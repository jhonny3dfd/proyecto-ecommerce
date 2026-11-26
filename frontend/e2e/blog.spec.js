import { test, expect } from '@playwright/test';

// Blog o portafolio (RF-01.1): el enlace del menú, la lista, una publicación y su galería

const configuracionBase = {
  nombre_tienda: 'Taller Maché',
  texto_bienvenida: 'Objetos con alma',
  texto_boton_ingreso: 'Ver piezas',
  tema_seleccionado: 1,
  nosotros_texto: 'Desde 2015 en Valparaíso.',
};

const foto = (n) => `http://127.0.0.1:5173/media/blog/foto-${n}.svg`;
const tarjeta = {
  titulo: 'Nuestro taller', slug: 'nuestro-taller', resumen: 'Cómo trabajamos',
  portada: foto(0), fecha_publicacion: '2026-10-23T12:00:00Z',
};
const publicacion = {
  ...tarjeta,
  contenido: '<p>Desde 2015 trabajamos el papel maché.</p>',
  fotos: [1, 2, 3].map((n) => ({ id: n, imagen: foto(n) })),
};

async function simularTienda(page, { blogActivo }) {
  // Sin banner de cookies: está fijo abajo y taparía los clics
  await page.addInitScript(() => localStorage.setItem('ecode_cookie_consent', 'rejected'));

  const responder = (route, data, status = 200) => route.fulfill({
    status, contentType: 'application/json', body: JSON.stringify(data),
  });

  // Simular la API sin modificar la base de datos
  await page.route('**/api/**', (route) => {
    const { pathname } = new URL(route.request().url());
    if (pathname === '/api/configuracion/') {
      return responder(route, { ...configuracionBase, blog_activo: blogActivo, blog_nombre: 'Portafolio' });
    }
    if (pathname === '/api/catalogo/vitrina/') return responder(route, { mas_vendidos: [], recientes: [] });
    if (pathname.startsWith('/api/ventas/blog/')) {
      if (!blogActivo) return responder(route, { detail: 'Esta página no está disponible.' }, 404);
      if (pathname === '/api/ventas/blog/') {
        return responder(route, { resultados: [tarjeta], total: 1, pagina: 1, paginas: 1 });
      }
      return responder(route, publicacion);
    }
    return responder(route, []);
  });

  await page.route('**/media/blog/*.svg', (route) => route.fulfill({
    contentType: 'image/svg+xml',
    body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><rect width="100%" height="100%" fill="#5B7A5E"/></svg>',
  }));
}

test('con el blog activo, el menú lleva a las publicaciones y a cada una', async ({ page }) => {
  await simularTienda(page, { blogActivo: true });
  await page.goto('/');

  const menu = page.getByRole('navigation', { name: 'Navegación de la tienda' });
  await menu.getByRole('link', { name: 'Portafolio' }).click();

  await expect(page).toHaveURL(/\/blog$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Portafolio' })).toBeVisible();

  await page.getByRole('link', { name: 'Nuestro taller' }).click();

  await expect(page).toHaveURL(/\/blog\/nuestro-taller$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Nuestro taller' })).toBeVisible();
  await expect(page.getByText('Desde 2015 trabajamos el papel maché.')).toBeVisible();
});

test('la galería se abre, se recorre con el teclado y devuelve el foco al cerrarla', async ({ page }) => {
  await simularTienda(page, { blogActivo: true });
  await page.goto('/blog/nuestro-taller');

  const segunda = page.getByRole('button', { name: 'Ver en grande: Foto 2 de 3 de "Nuestro taller"' });
  await segunda.click();

  const visor = page.getByRole('dialog', { name: 'Galería de "Nuestro taller"' });
  await expect(visor).toBeVisible();
  await expect(visor.getByRole('button', { name: 'Cerrar' })).toBeFocused();
  await expect(visor.getByText('2 de 3')).toBeVisible();

  await page.keyboard.press('ArrowRight');
  await expect(visor.getByText('3 de 3')).toBeVisible();

  await page.keyboard.press('Escape');
  await expect(visor).toBeHidden();
  await expect(segunda).toBeFocused();
});

test('con el blog apagado, "Nosotros" lleva a la landing y /blog no muestra contenido', async ({ page }) => {
  await simularTienda(page, { blogActivo: false });
  await page.goto('/');

  const menu = page.getByRole('navigation', { name: 'Navegación de la tienda' });
  await expect(menu.getByRole('link', { name: 'Nosotros' })).toHaveAttribute('href', '/#nosotros');
  await expect(menu.getByRole('link', { name: 'Portafolio' })).toHaveCount(0);

  await page.goto('/blog');
  await expect(page.getByRole('heading', { name: 'Esta página no está disponible' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Nuestro taller' })).toHaveCount(0);
});

test('en un teléfono el blog no se desborda hacia el costado', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await simularTienda(page, { blogActivo: true });

  for (const ruta of ['/blog', '/blog/nuestro-taller']) {
    await page.goto(ruta);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    const desborde = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(desborde, ruta).toBe(0);
  }
});
