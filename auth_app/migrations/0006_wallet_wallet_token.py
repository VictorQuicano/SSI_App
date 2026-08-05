from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0005_evtol_fields_and_vertiport'),
    ]

    operations = [
        migrations.AddField(
            model_name='wallet',
            name='wallet_token',
            field=models.TextField(blank=True, null=True),
        ),
    ]
