from django.test import SimpleTestCase

from ecommerce.application.vitrina import (
    CatalogoVitrina, PublicacionesVitrina, SeleccionarVitrina, ValidarDestacados, VentasPorProducto,
)
from ecommerce.domain.destacados import DestacadosInvalidos, ModoVitrina


class VentasFalsas(VentasPorProducto):
    def __init__(self, ranking):
        self.ranking = ranking

    def mas_vendidos(self, limite):
        return self.ranking[:limite]


class CatalogoFalso(CatalogoVitrina):
    def __init__(self, visibles_del_mas_nuevo_al_mas_viejo, borradores=()):
        self.productos = visibles_del_mas_nuevo_al_mas_viejo
        self.borradores = list(borradores)

    def visibles(self, ids):
        return [i for i in ids if i in self.productos]

    def recientes(self, limite, excluir=()):
        return [i for i in self.productos if i not in excluir][:limite]

    def existentes(self, ids):
        return [i for i in ids if i in self.productos or i in self.borradores]


class PublicacionesFalsas(PublicacionesVitrina):
    def __init__(self, publicadas=(), borradores=()):
        self.publicadas = list(publicadas)
        self.borradores = list(borradores)
        self.consultas = 0

    def visibles(self, ids):
        self.consultas += 1
        return [i for i in ids if i in self.publicadas]

    def existentes(self, ids):
        return [i for i in ids if i in self.publicadas or i in self.borradores]


class VentasQueNoSeConsultan(VentasPorProducto):
    def mas_vendidos(self, limite):
        raise AssertionError('Con destacados visibles no se calculan los más vendidos')


def producto(id_producto):
    return {'tipo': 'PRODUCTO', 'id': id_producto}


def publicacion(id_publicacion):
    return {'tipo': 'PUBLICACION', 'id': id_publicacion}


def vitrina(ranking, catalogo, cantidad=4):
    return SeleccionarVitrina(VentasFalsas(ranking), CatalogoFalso(catalogo), cantidad).ejecutar()


class SeleccionarVitrinaTests(SimpleTestCase):
    """RF-01.1: la landing muestra los más vendidos y los últimos agregados."""

    def test_los_mas_vendidos_siguen_el_ranking_de_ventas(self):
        resultado = vitrina(['c', 'a', 'f', 'b', 'e'], ['a', 'b', 'c', 'd', 'e', 'f'])

        self.assertEqual(resultado.mas_vendidos, ['c', 'a', 'f', 'b'])
        self.assertEqual(resultado.recientes, ['a', 'b', 'c', 'd'])

    def test_un_producto_vendido_que_ya_no_esta_publicado_no_aparece(self):
        resultado = vitrina(['oculto', 'c', 'borrado', 'a', 'b', 'd'], ['a', 'b', 'c', 'd'])

        self.assertEqual(resultado.mas_vendidos, ['c', 'a', 'b', 'd'])

    def test_sin_ventas_se_completa_primero_con_productos_que_no_estan_en_ultimos_agregados(self):
        resultado = vitrina([], ['n1', 'n2', 'n3', 'n4', 'v1', 'v2', 'v3', 'v4', 'v5'])

        self.assertEqual(resultado.recientes, ['n1', 'n2', 'n3', 'n4'])
        self.assertEqual(resultado.mas_vendidos, ['v1', 'v2', 'v3', 'v4'])

    def test_con_pocas_ventas_se_completa_sin_repetir_los_vendidos(self):
        resultado = vitrina(['v3'], ['n1', 'n2', 'n3', 'n4', 'v1', 'v2', 'v3'])

        self.assertEqual(resultado.mas_vendidos, ['v3', 'v1', 'v2', 'n1'])

    def test_con_un_catalogo_chico_se_repiten_productos_antes_que_dejar_la_seccion_corta(self):
        resultado = vitrina([], ['a', 'b'])

        self.assertEqual(resultado.recientes, ['a', 'b'])
        self.assertEqual(sorted(resultado.mas_vendidos), ['a', 'b'])

    def test_sin_productos_publicados_las_dos_secciones_quedan_vacias(self):
        resultado = vitrina(['a'], [])

        self.assertEqual((resultado.mas_vendidos, resultado.recientes), ([], []))


def con_destacados(destacados, catalogo=('a', 'b', 'c', 'd', 'e'), publicadas=('1', '2'), blog_activo=True,
                   modo=ModoVitrina.DESTACADOS, ventas=None):
    publicaciones = PublicacionesFalsas(publicadas)
    caso = SeleccionarVitrina(ventas or VentasFalsas(['e', 'd']), CatalogoFalso(list(catalogo)),
                              publicaciones=publicaciones)
    return caso.ejecutar(modo, destacados, blog_activo), publicaciones


class DestacadosTests(SimpleTestCase):
    """RF-01.1, pedido de un cliente: el admin elige a mano lo que se muestra en vez de "Más vendidos"."""

    def test_por_defecto_la_vitrina_sigue_mostrando_los_mas_vendidos(self):
        resultado = vitrina(['c', 'a'], ['a', 'b', 'c', 'd'])

        self.assertEqual(resultado.destacados, [])
        self.assertEqual(resultado.mas_vendidos[:2], ['c', 'a'])

    def test_con_el_modo_mas_vendidos_se_ignoran_los_destacados_guardados(self):
        resultado, _ = con_destacados([producto('a')], modo=ModoVitrina.MAS_VENDIDOS)

        self.assertEqual(resultado.destacados, [])
        self.assertEqual(resultado.mas_vendidos[:2], ['e', 'd'])

    def test_mezcla_productos_y_publicaciones_en_el_orden_elegido_sin_calcular_los_mas_vendidos(self):
        elegidos = [publicacion('2'), producto('c'), publicacion('1'), producto('a')]
        resultado, _ = con_destacados(elegidos, ventas=VentasQueNoSeConsultan())

        self.assertEqual(resultado.destacados, elegidos)
        self.assertEqual(resultado.mas_vendidos, [])
        # "Últimos agregados" no cambia
        self.assertEqual(resultado.recientes, ['a', 'b', 'c', 'd'])

    def test_un_producto_despublicado_o_una_publicacion_en_borrador_desaparecen_sin_romper_la_seccion(self):
        resultado, _ = con_destacados([producto('oculto'), publicacion('borrador'), producto('b'), publicacion('1')])

        self.assertEqual(resultado.destacados, [producto('b'), publicacion('1')])

    def test_con_el_blog_apagado_las_publicaciones_no_se_muestran(self):
        resultado, publicaciones = con_destacados([publicacion('1'), producto('a')], blog_activo=False)

        self.assertEqual(resultado.destacados, [producto('a')])
        self.assertEqual(publicaciones.consultas, 0)

    def test_si_no_queda_ninguno_visible_vuelven_los_mas_vendidos(self):
        resultado, _ = con_destacados([producto('borrado'), publicacion('1')], blog_activo=False)

        self.assertEqual(resultado.destacados, [])
        self.assertEqual(resultado.mas_vendidos[:2], ['e', 'd'])

    def test_una_seleccion_guardada_con_otra_forma_no_rompe_la_landing(self):
        resultado, _ = con_destacados([{'tipo': 'CATEGORIA', 'id': 'x'}])

        self.assertEqual(resultado.destacados, [])
        self.assertEqual(len(resultado.mas_vendidos), 4)


class ValidarDestacadosTests(SimpleTestCase):
    def validar(self, lista):
        catalogo = CatalogoFalso(['a', 'b'], borradores=['sin-publicar'])
        return ValidarDestacados(catalogo, PublicacionesFalsas(['1'], borradores=['2'])).ejecutar(lista)

    def test_acepta_productos_y_publicaciones_que_existen_aunque_no_esten_publicados(self):
        lista = [producto('sin-publicar'), publicacion('2'), producto('a'), {'tipo': 'PUBLICACION', 'id': 1}]

        self.assertEqual(self.validar(lista), [producto('sin-publicar'), publicacion('2'), producto('a'),
                                               publicacion('1')])

    def test_rechaza_un_producto_o_una_publicacion_que_no_existe(self):
        for lista in ([producto('borrado')], [publicacion('99')], [producto('a'), publicacion('99')]):
            with self.subTest(lista=lista), self.assertRaisesMessage(DestacadosInvalidos, 'ya no existe'):
                self.validar(lista)

    def test_aplica_las_reglas_del_dominio(self):
        with self.assertRaisesMessage(DestacadosInvalidos, 'dos veces'):
            self.validar([producto('a'), producto('a')])
        # 9 que existen: el límite de 8 se aplica antes de buscarlos
        nueve = [producto(letra) for letra in 'abcdefg'] + [publicacion('1'), publicacion('2')]
        validar = ValidarDestacados(CatalogoFalso(list('abcdefg')), PublicacionesFalsas(['1', '2'])).ejecutar
        with self.assertRaisesMessage(DestacadosInvalidos, 'hasta 8'):
            validar(nueve)
        self.assertEqual(validar(nueve[:8]), nueve[:8])

    def test_una_lista_vacia_es_valida(self):
        self.assertEqual(self.validar([]), [])
