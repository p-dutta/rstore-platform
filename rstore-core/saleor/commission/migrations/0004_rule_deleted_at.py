# Generated by Django 3.0.6 on 2021-01-03 10:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commission', '0003_rulehistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='rule',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
