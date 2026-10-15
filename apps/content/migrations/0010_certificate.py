# Generated manually
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0009_faq_alter_instructor_options_instructor_bio_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Certificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('certificate_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('student_name', models.CharField(blank=True, max_length=255, null=True)),
                ('related_course', models.CharField(blank=True, max_length=255, null=True)),
                ('instructor_name', models.CharField(blank=True, max_length=255, null=True)),
                ('issuing_organization', models.CharField(default='RootsExams', max_length=255)),
                ('issue_date', models.DateField(blank=True, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('image', models.URLField(blank=True, max_length=500, null=True)),
                ('pdf_url', models.URLField(blank=True, max_length=500, null=True)),
                ('is_featured', models.BooleanField(default=False)),
                ('is_verified', models.BooleanField(default=True)),
                ('status', models.IntegerField(choices=[(1, 'Active'), (0, 'Inactive')], default=1)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificates', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Certificate',
                'verbose_name_plural': 'Certificates',
                'db_table': 'certificates',
                'ordering': ['order', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='certificate',
            index=models.Index(fields=['status', 'is_featured'], name='certificate_status_a2a672_idx'),
        ),
        migrations.AddIndex(
            model_name='certificate',
            index=models.Index(fields=['certificate_id'], name='certificate_certifi_a0a669_idx'),
        ),
        migrations.AddIndex(
            model_name='certificate',
            index=models.Index(fields=['student_name'], name='certificate_student_bcb5ff_idx'),
        ),
    ]
