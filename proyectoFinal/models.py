from django.contrib.auth.models import User
from django.db import models

# Create your models here.

from django.db import models


class Rutas(models.Model):
    titulo = models.CharField(max_length=45)
    fecha = models.DateField()
    tiempo = models.TimeField()
    distancia = models.DecimalField(max_digits=5, decimal_places=2)
    velocidad = models.DecimalField(max_digits=5, decimal_places=2)
    ascenso = models.IntegerField()
    descenso = models.IntegerField()
    dureza = models.CharField(max_length=45)
    imagen = models.ImageField(upload_to="proyectoFinal", null=True, blank=True)
    # imagen = models.CharField(max_length=100, blank=True, null=True)
    idUsuario = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.titulo} - {self.idUsuario.first_name}"
