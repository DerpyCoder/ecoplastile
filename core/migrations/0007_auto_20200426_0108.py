# Generated by Django 3.0.5 on 2020-04-26 06:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_item_quantitiy'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='item',
            name='quantitiy',
        ),
        migrations.AddField(
            model_name='orderitem',
            name='quantitiy',
            field=models.IntegerField(default=1),
        ),
    ]