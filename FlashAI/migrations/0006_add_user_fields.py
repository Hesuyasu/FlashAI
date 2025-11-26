from django.db import migrations, models
import django.conf


class Migration(migrations.Migration):

    dependencies = [
        ('FlashAI', '0005_flashcard_mcq_fields'),
        ('auth', '__latest__'),
    ]

    operations = [
        migrations.AddField(
            model_name='flashcard',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=models.deletion.CASCADE, related_name='flashcards', to=django.conf.settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='pdfdocument',
            name='user',
            field=models.ForeignKey(null=True, blank=True, on_delete=models.deletion.CASCADE, related_name='pdfs', to=django.conf.settings.AUTH_USER_MODEL),
        ),
    ]
