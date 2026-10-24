from rest_framework import serializers

from core.models import AutomationLog


class AutomationLogInputSerializer(serializers.Serializer):
    workflow_name = serializers.CharField(max_length=250)
    event_type = serializers.CharField(max_length=100)
    status = serializers.ChoiceField(choices=[c[0] for c in AutomationLog.STATUS_CHOICES])
    message = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")


class DailyReportInputSerializer(serializers.Serializer):
    date = serializers.DateField(required=False, help_text="YYYY-MM-DD; defaults to the latest day with orders")
