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
    publico = models.BooleanField(default=False)
    # imagen = models.CharField(max_length=100, blank=True, null=True)
    idUsuario = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.titulo} - {self.idUsuario.first_name}"


class tiposBicicletas(models.Model):
    nombre_tipo = models.CharField(max_length=50, unique=True)
    tipoNeumatico = models.CharField(max_length=45)


class caracteristicas(models.Model):
    edad = models.PositiveIntegerField()
    estatura = models.DecimalField(max_digits=3, decimal_places=2)
    peso = models.DecimalField(max_digits=5, decimal_places=2)
    estado = models.PositiveSmallIntegerField()
    suelo = models.PositiveSmallIntegerField()
    # tipo_bici = models.PositiveSmallIntegerField()
    tipo_bici = models.ForeignKey(tiposBicicletas, on_delete=models.CASCADE, null=True, blank=True)
    usuario_id = models.OneToOneField(User, on_delete=models.CASCADE)
