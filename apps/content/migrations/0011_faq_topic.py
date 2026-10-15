from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0010_certificate'),
    ]

    operations = [
        migrations.AddField(
            model_name='faq',
            name='topic',
            field=models.CharField(default='general', max_length=100),
            preserve_default=False,
        ),
    ]
