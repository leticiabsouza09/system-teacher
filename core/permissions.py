"""
Permissões customizadas do DRF — reutilizadas em todos os ViewSets a
partir da Etapa 5. Centralizadas aqui (não em cada app) porque as mesmas
3 regras se repetem em quase todo endpoint: são a espinha dorsal da
Seção 16 (permissões) e da Seção 3 (o que cada perfil pode fazer).

Regra de ouro seguida em toda permissão abaixo: NUNCA decidir com base em
dado que o cliente envia (ex.: um campo "role" no corpo da requisição) —
sempre a partir de request.user, que já veio autenticado e verificado
pelo próprio Django. Confiar em dado do cliente pra controle de acesso é
a forma mais comum de furo de autorização.
"""
from rest_framework import permissions

from users.models import User


class IsStudent(permissions.BasePermission):
    """Só usuários com role=student passam."""
    message = "Esta ação é permitida apenas para alunos."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_student)


class IsTeacher(permissions.BasePermission):
    """Só usuários com role=teacher passam."""
    message = "Esta ação é permitida apenas para professores."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_teacher)


class IsAdminRole(permissions.BasePermission):
    """Só usuários com role=admin passam (diferente de is_staff do Django,
    que também dá acesso ao /admin/ — um admin do sistema tem as duas coisas,
    normalmente, mas a checagem de negócio é sempre pelo role)."""
    message = "Esta ação é permitida apenas para administradores."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == User.Role.ADMIN)


class IsOwnerStudent(permissions.BasePermission):
    """Objeto só é acessível pelo próprio aluno dono dele. Espera que o
    model tenha um campo `student` (FK para User) — é o caso de Assessment,
    Diagnostic, StudentSkill, StudyPlan, ActivityAttempt, ProgressRecord.
    'Aluno não vê dados de outro aluno' (Seção 16) é isto, objeto a objeto,
    não só uma checagem de lista."""
    message = "Você só pode acessar seus próprios dados."

    def has_object_permission(self, request, view, obj):
        student = getattr(obj, "student", None)
        return student is not None and student_id_matches(student, request.user)


class IsTeacherOfStudent(permissions.BasePermission):
    """Um professor só acessa dados de um aluno se existir pelo menos um
    TeacherFeedback, StudyPlan aprovado por ele, ou Diagnostic validado por
    ele envolvendo aquele aluno — nesta primeira versão do MVP, simplificamos
    para: QUALQUER professor autenticado pode ver QUALQUER aluno (não há
    ainda o conceito de "turma"/vínculo formal professor-aluno nos models
    da Etapa 3). Isolei essa regra aqui, comentada, para não se perder: é
    o primeiro ponto a evoluir quando o model de Turma existir."""
    message = "Você não tem vínculo com este aluno."

    def has_object_permission(self, request, view, obj):
        if not (request.user.is_authenticated and request.user.is_teacher):
            return False
        # TODO(etapa-futura): restringir por vínculo real professor-aluno
        # (ex.: turma em comum) assim que esse model existir.
        return True


class IsTeacherOrReadOnlyOwner(permissions.BasePermission):
    """Usado em endpoints como Diagnostic e StudyPlan: o professor pode
    fazer qualquer ação (inclusive aprovar/editar); o aluno dono só pode
    LER (GET) — nunca aprovar o próprio diagnóstico ou editar o próprio
    plano. Isso é o que impede, em código, o cenário 'aluno não consegue
    aprovar diagnóstico' que a Seção 16 pede para testar."""
    message = "Apenas o professor pode aprovar, editar ou modificar este recurso."

    def has_object_permission(self, request, view, obj):
        if request.user.is_teacher:
            return True
        if request.method in permissions.SAFE_METHODS:
            student = getattr(obj, "student", None)
            return student is not None and student_id_matches(student, request.user)
        return False


def student_id_matches(student: User, request_user: User) -> bool:
    """Pequeno helper para deixar as comparações acima legíveis e num
    único lugar — se amanhã "aluno" deixar de ser comparado por PK direto
    (ex.: vier a ser comparado por um StudentProfile.id), muda só aqui."""
    return student.pk == request_user.pk
