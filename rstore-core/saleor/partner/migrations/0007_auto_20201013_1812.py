# Generated by Django 3.0.6 on 2020-10-13 12:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner', '0006_partner_partner_app'),
    ]

    operations = [
        migrations.AddField(
            model_name='partner',
            name='base_url',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='partner',
            name='web_origins',
            field=models.TextField(blank=True, default=[]),
        ),
    ]
