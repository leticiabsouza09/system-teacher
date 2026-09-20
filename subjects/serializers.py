from rest_framework import serializers

from .models import Skill, Subject


class SkillSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    prerequisite_names = serializers.SlugRelatedField(
        source="prerequisites", slug_field="name", many=True, read_only=True)

    class Meta:
        model = Skill
        fields = ["id", "subject", "subject_name", "name", "description",
                  "difficulty_level", "prerequisites", "prerequisite_names"]
        extra_kwargs = {"prerequisites": {"write_only": True}}


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "description"]
