"""Reglas de configuración del menú, independientes de Django y de la persistencia."""

# 'suscripcion' (pedido de un cliente, opcional): solo se ve con el módulo de suscripciones activo
ORDEN_MENU = ('inicio', 'catalogo', 'nosotros', 'sobre_mi', 'cotizar', 'suscripcion')
ENLACES_MENU = frozenset(ORDEN_MENU)
ENLACES_OCULTABLES = frozenset({'nosotros', 'sobre_mi', 'cotizar', 'suscripcion'})
ENLACES_RENOMBRABLES = frozenset({'catalogo'})
MAXIMO_NOMBRE_CATALOGO = 20


class MenuInvalido(ValueError):
    """La configuración del menú incumple una regla de negocio."""


def normalizar_menu_principal(valor, menu_anterior=None) -> dict:
    if not isinstance(valor, dict) or set(valor) - {'orden', 'nombres', 'ocultos'}:
        raise MenuInvalido('La configuración debe contener solo orden, nombres y ocultos.')
    resultado = {}
    if 'orden' in valor:
        orden = valor['orden']
        if (not isinstance(orden, list)
                or any(not isinstance(item, str) for item in orden)
                or set(orden) - ENLACES_MENU
                or len(set(orden)) != len(orden)):
            raise MenuInvalido('El orden debe contener enlaces conocidos, de texto y sin duplicados.')
        resultado['orden'] = orden + [enlace for enlace in ORDEN_MENU if enlace not in orden]
    if 'nombres' in valor:
        # Solo se renombra "Catálogo": el blog y Sobre mí tienen su nombre en su propio módulo, y los demás son fijos
        nombres = valor['nombres']
        if not isinstance(nombres, dict) or set(nombres) - ENLACES_MENU:
            raise MenuInvalido('Los nombres contienen enlaces desconocidos.')
        resultado['nombres'] = {}
        for clave, nombre in nombres.items():
            if not isinstance(nombre, str):
                raise MenuInvalido('Cada nombre debe ser texto.')
            nombre = ' '.join(nombre.split())
            # Un nombre guardado antes (de otro botón, o un Catálogo más largo) se conserva mientras no cambie;
            # la tienda solo muestra el de Catálogo
            anterior = (menu_anterior or {}).get('nombres', {}).get(clave)
            sin_cambios = isinstance(anterior, str) and nombre == ' '.join(anterior.split())
            if clave not in ENLACES_RENOMBRABLES:
                if not sin_cambios:
                    raise MenuInvalido('Solo se puede cambiar el nombre de Catálogo.')
                resultado['nombres'][clave] = anterior
            elif len(nombre) > MAXIMO_NOMBRE_CATALOGO:
                if not sin_cambios:
                    raise MenuInvalido(f'El nombre no puede superar los {MAXIMO_NOMBRE_CATALOGO} caracteres.')
                resultado['nombres'][clave] = anterior
            elif nombre:
                resultado['nombres'][clave] = nombre
    if 'ocultos' in valor:
        ocultos = valor['ocultos']
        if (not isinstance(ocultos, list)
                or any(not isinstance(item, str) for item in ocultos)
                or set(ocultos) - ENLACES_OCULTABLES
                or len(set(ocultos)) != len(ocultos)):
            raise MenuInvalido('Solo se pueden ocultar enlaces opcionales, sin duplicados.')
        resultado['ocultos'] = ocultos
    return resultado
