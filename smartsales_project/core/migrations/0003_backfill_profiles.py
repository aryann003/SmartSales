from django.db import migrations


def create_missing_profiles(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("core", "Profile")
    for user in User.objects.filter(profile__isnull=True):
        Profile.objects.create(user=user, role="admin" if user.is_superuser else "salesperson")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_automationlog"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(create_missing_profiles, migrations.RunPython.noop)]
