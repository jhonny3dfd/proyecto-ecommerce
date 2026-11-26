# Ecode
Proyecto de desarrollo de software para una empresa que cuenta con un e-commerce. El objetivo es desarrollar una solución que responda a las necesidades y requerimientos de la empresa.

Este proyecto se desarrolla en el marco de la asignatura Consultoría de Empresas.

## Equipo

* Cristóbal Quezada
* Emilio San Martín
* Giuliana Zúñiga
* Eidan Huisicán
* Luciano Araya
* Jhonatan de la Cruz
* Javier Vallejos

## Tecnologías

Por definir.

## Metodología de trabajo

El proyecto será desarrollado de manera colaborativa, organizando el trabajo en diferentes Sprints.

Cada integrante trabajará en su propia rama personal. La rama personal será utilizada para desarrollar y posteriormente integrar los cambios mediante Pull Requests hacia la rama correspondiente al Sprint.

## Estructura de ramas

La rama `main` contendrá la versión estable del proyecto.

Cada Sprint contará con su propia rama y los integrantes trabajarán mediante ramas personales.

```text
main
└── sprint-0
    ├── cristobal
    ├── emilio
    ├── juliana
    ├── eidan
    ├── luciano
    ├── jonathan
    └── javier
```

A medida que avance el proyecto se crearán nuevas ramas para los siguientes Sprints.

## Flujo de trabajo

### 1. Actualizar la rama personal

Antes de comenzar a trabajar, cada integrante debe asegurarse de tener su rama actualizada con los últimos cambios disponibles.

```bash
git checkout cristobal
git pull
```

Cada integrante debe reemplazar `cristobal` por el nombre de su propia rama.

### 2. Realizar los cambios

Cada integrante desarrolla las funcionalidades o tareas asignadas dentro de su rama personal.

Durante el desarrollo se puede revisar el estado de los archivos con:

```bash
git status
```

### 3. Agregar los cambios

Una vez finalizado el cambio, se agregan los archivos modificados:

```bash
git add .
```

También se puede agregar un archivo específico:

```bash
git add nombre-del-archivo
```

### 4. Crear el commit

Después de agregar los cambios, se crea un commit con un mensaje descriptivo:

```bash
git commit -m "Descripción del cambio realizado"
```

Por ejemplo:

```bash
git commit -m "Implementa formulario de inicio de sesión"
```

### 5. Subir los cambios a GitHub

Una vez realizado el commit, se suben los cambios a la rama personal:

```bash
git push origin cristobal
```

Cada integrante debe reemplazar `cristobal` por el nombre de su propia rama.

### 6. Crear un Pull Request

Una vez que los cambios fueron subidos a GitHub, se debe crear un Pull Request desde la rama personal hacia la rama correspondiente al Sprint.

Por ejemplo:

```text
cristobal → sprint-0
```

### 7. Revisión de los cambios

El Pull Request debe ser revisado por los integrantes correspondientes.

Se verificará que los cambios funcionen correctamente y que no generen problemas con el trabajo realizado por los demás integrantes.

Si se encuentran problemas, el integrante responsable deberá realizar las modificaciones necesarias en su rama.

Los nuevos cambios se podrán subir mediante:

```bash
git add .
git commit -m "Corrige observaciones de revisión"
git push origin cristobal
```

El Pull Request se actualizará automáticamente.

### 8. Integración a la rama del Sprint

Una vez que los cambios hayan sido revisados y aprobados, se realizará el merge del Pull Request hacia la rama correspondiente al Sprint.

El flujo será:

```text
Rama personal
      ↓
Desarrollo
      ↓
git add
      ↓
git commit
      ↓
git push
      ↓
Pull Request
      ↓
Revisión
      ↓
Aprobación
      ↓
Merge
      ↓
Rama del Sprint
```

### 9. Finalización del Sprint

Una vez que todos los cambios del Sprint hayan sido integrados, se realizarán las pruebas correspondientes.

Cuando el Sprint se encuentre terminado y estable, se podrá integrar a `main` mediante un Pull Request.

## Seguridad y contratos de acceso

La suite de seguridad se ejecuta con `python manage.py test` y PostgreSQL de
pruebas. Consultar [alcance, configuración y matriz QA](docs/security-qa.md) y
el [contrato OpenAPI de autenticación](docs/openapi.json), que documenta las
rutas reales de registro, login JWT, renovación de tokens y Google SSO.

Los endpoints de galerías de producto, límites de subida y flujo de integración
para los formularios React se documentan en
[Imágenes del catálogo (SCRUM-125)](docs/IMAGENES_CATALOGO.md). La suite completa
usa PostgreSQL y MongoDB reales, con bases de prueba aisladas.

## Estado del proyecto

En desarrollo — Sprint 0.
