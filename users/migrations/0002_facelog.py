# Generated by Django 5.1.6 on 2025-02-12 12:45

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FaceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('face_encoding', models.JSONField(verbose_name="Yuz kodlash ma'lumotlari")),
                ('emotion', models.CharField(blank=True, max_length=50, null=True, verbose_name='Hissiy holat')),
                ('face_landmarks', models.JSONField(blank=True, null=True, verbose_name='Yuz landmarks')),
                ('detected_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Aniqlangan vaqt')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='face_logs', to=settings.AUTH_USER_MODEL, verbose_name='Foydalanuvchi')),
            ],
        ),
    ]
