"""
Permissões customizadas do DRF — reutilizadas em todos os ViewSets a
partir da Etapa 5. Centralizadas aqui (não em cada app) porque as mesmas
regras se repetem em quase todo endpoint: são a espinha dorsal da
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


class IsTeacherOrAdmin(permissions.BasePermission):
    """Professor OU admin — usado onde ambos podem agir, mas aluno não
    (ex.: criar uma Classroom nova)."""
    message = "Esta ação é permitida apenas para professores ou administradores."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_teacher or u.role == User.Role.ADMIN))


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


def teacher_has_classroom_with(teacher: User, student: User) -> bool:
    """A checagem central de vínculo real professor↔aluno — via Classroom.
    Usada tanto nas permissões abaixo quanto nos querysets dos ViewSets
    (students, learning, assessments, dashboard), pra nunca ter dois
    lugares decidindo isso de formas diferentes. Antes deste helper
    existir, TODO professor via TODO aluno — essa era a limitação
    documentada desde a Etapa 4."""
    from classrooms.models import Classroom
    return Classroom.objects.filter(teachers=teacher, students=student).exists()


class IsTeacherOfStudent(permissions.BasePermission):
    """Um professor só acessa dados de um aluno que está numa Classroom
    que ele leciona — vínculo real agora, não mais 'qualquer professor
    vê qualquer aluno'."""
    message = "Você não tem vínculo com este aluno."

    def has_object_permission(self, request, view, obj):
        if not (request.user.is_authenticated and request.user.is_teacher):
            return False
        aluno = obj if isinstance(obj, User) else getattr(obj, "student", None)
        return aluno is not None and teacher_has_classroom_with(request.user, aluno)


class IsTeacherOrReadOnlyOwner(permissions.BasePermission):
    """Usado em endpoints como Diagnostic e StudyPlan: o professor só pode
    aprovar/editar se tiver vínculo de Classroom com o aluno dono do
    objeto; o aluno dono só pode LER (GET) — nunca aprovar o próprio
    diagnóstico ou editar o próprio plano (Seção 16)."""
    message = "Apenas um professor vinculado a este aluno pode aprovar, editar ou modificar este recurso."

    def has_object_permission(self, request, view, obj):
        student = getattr(obj, "student", None)
        if request.user.is_teacher:
            return student is not None and teacher_has_classroom_with(request.user, student)
        if request.method in permissions.SAFE_METHODS:
            return student is not None and student_id_matches(student, request.user)
        return False


def student_id_matches(student: User, request_user: User) -> bool:
    """Pequeno helper para deixar as comparações acima legíveis e num
    único lugar — se amanhã "aluno" deixar de ser comparado por PK direto
    (ex.: vier a ser comparado por um StudentProfile.id), muda só aqui."""
    return student.pk == request_user.pk
