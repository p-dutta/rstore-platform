# Generated by Django 3.0.6 on 2020-10-19 09:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notification', '0002_segment_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='schedule',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='updated',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='segment',
            name='updated',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
