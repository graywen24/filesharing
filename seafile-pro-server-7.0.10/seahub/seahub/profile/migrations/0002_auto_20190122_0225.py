# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2019-01-22 02:25
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('profile', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='contact_email',
            field=models.EmailField(blank=True, max_length=225, null=True, unique=True),
        ),
    ]
