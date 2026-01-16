from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Feedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.BooleanField(help_text='True for thumbs up, False for thumbs down')),
                ('note', models.TextField(blank=True, help_text='Optional note explaining the feedback', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('message', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='chat.message')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
