# Generated by Django 5.2 on 2025-04-25 12:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_camera_hardware_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='camera',
            name='password',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Parol'),
        ),
        migrations.AddField(
            model_name='camera',
            name='username',
            field=models.CharField(blank=True, max_length=100, null=True, verbose_name='Foydalanuvchi nomi'),
        ),
    ]
