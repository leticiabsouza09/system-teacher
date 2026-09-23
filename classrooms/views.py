"""
ViewSet de Classroom (Turma).

Regras de segurança que valem a pena destacar (é fácil errar aqui e abrir
um jeito de um professor entrar numa turma que não é dele):

- Professor só LISTA/EDITA as próprias turmas — get_queryset já filtra
  antes de qualquer permissão de objeto rodar (mesmo padrão 404-em-vez-
  de-403 usado no resto do projeto).
- Criar turma: qualquer professor pode, mas o campo `teachers` do payload
  é DESCARTADO se quem pede não for admin — o próprio professor que criou
  é adicionado automaticamente. Sem isso, um professor poderia se auto-
  atribuir a criação alegando que outro colega é o responsável, ou até
  tentar se colar em uma lista de professores arbitrária.
- Editar `teachers` (trocar quem é responsável pela turma) exige admin —
  um professor não pode se auto-promover a dono de uma turma que já
  existe, nem remover outro professor dela.
- Adicionar/remover aluno é feito por USERNAME (não por uma lista de
  todos os alunos do sistema) — evitar dar a qualquer professor acesso de
  navegação pelo cadastro completo de alunos, que violaria a mesma
  privacidade aplicada em todo o resto do projeto.
- Excluir turma: só admin.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsTeacherOrAdmin
from users.models import User

from .models import Classroom
from .serializers import ClassroomSerializer


class ClassroomViewSet(viewsets.ModelViewSet):
    serializer_class = ClassroomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        base = Classroom.objects.all().prefetch_related("teachers", "students")
        user = self.request.user
        if user.role == User.Role.ADMIN:
            return base
        if user.is_teacher:
            return base.filter(teachers=user)
        return Classroom.objects.none()  # aluno não gerencia turma

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsTeacherOrAdmin()]
        return super().get_permissions()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == User.Role.ADMIN:
            serializer.save()
            return
        # 'students' também precisa ser descartado aqui — sem isso, um
        # professor poderia mandar um PATCH genérico com uma lista de ids
        # e substituir o roster inteiro de uma vez, driblando completamente
        # o add-student/remove-student (que é por username, um de cada
        # vez, de propósito). Mesma trava que já existia só pra 'teachers'.
        serializer.validated_data.pop("teachers", None)
        serializer.validated_data.pop("students", None)
        classroom = serializer.save()
        classroom.teachers.add(user)

    def perform_update(self, serializer):
        if self.request.user.role != User.Role.ADMIN:
            serializer.validated_data.pop("teachers", None)
            serializer.validated_data.pop("students", None)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Apenas administrador pode excluir turmas."},
                             status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="add-student")
    def add_student(self, request, pk=None):
        turma = self.get_object()  # já filtrado por get_queryset — 404 se não for sua turma
        username = request.data.get("username", "").strip()
        if not username:
            return Response({"username": ["Obrigatório."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            aluno = User.objects.get(username=username, role=User.Role.STUDENT)
        except User.DoesNotExist:
            return Response({"detail": "Nenhum aluno com esse username."}, status=status.HTTP_404_NOT_FOUND)
        turma.students.add(aluno)
        return Response(ClassroomSerializer(turma).data)

    @action(detail=True, methods=["post"], url_path="remove-student")
    def remove_student(self, request, pk=None):
        turma = self.get_object()
        username = request.data.get("username", "").strip()
        try:
            aluno = turma.students.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "Esse aluno não está nesta turma."}, status=status.HTTP_404_NOT_FOUND)
        turma.students.remove(aluno)
        return Response(ClassroomSerializer(turma).data)
