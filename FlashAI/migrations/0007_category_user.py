from django.db import migrations, models
import django.conf
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('FlashAI', '0006_add_user_fields'),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.CASCADE, related_name='categories', to=django.conf.settings.AUTH_USER_MODEL),
        ),
    ]
