from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('FlashAI', '0004_remove_studystreak_user_delete_studysession_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='flashcard',
            name='option_a',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='flashcard',
            name='option_b',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='flashcard',
            name='option_c',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='flashcard',
            name='option_d',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='flashcard',
            name='correct_option',
            field=models.CharField(blank=True, choices=[('A','A'),('B','B'),('C','C'),('D','D')], max_length=1),
        ),
    ]
