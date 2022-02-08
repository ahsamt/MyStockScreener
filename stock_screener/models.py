from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.fields import AutoField
import django.utils


class User(AbstractUser):
    pass
