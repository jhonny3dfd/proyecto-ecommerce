// Servicios QA reales de Django, PostgreSQL y MongoDB, sin sustituir respuestas de la API.
import { test, expect } from '@playwright/test';
import process from 'node:process';

test.beforeAll(async ({ request }) => {
  const names = ['QA149_POSTGRES_PASSWORD', 'QA149_SECRET_KEY', 'QA149_CLAVE_CIFRADO_CREDENCIALES',
    'QA149_ADMIN_EMAIL', 'QA149_ADMIN_PASSWORD'];
  const missing = names.filter((name) => !process.env[name]?.trim());
  if (missing.length) throw new Error(`Faltan variables de QA: ${missing.join(', ')}. Configure tools/qa/scrum149/.env.local o la sesión.`);
  const response = await request.get('http://127.0.0.1:8000/api/catalogo/productos/');
  expect(response.ok(), 'El backend QA aislado debe estar disponible').toBeTruthy();
  const catalog = await response.json();
  expect(catalog.count, 'Se requiere el fixture QA149; no ejecutar sobre datos de desarrollo').toBe(1080);
  expect(catalog.results[0].nombre).toMatch(/^Producto QA149 /);
});

async function checkLayout(page) {
  const layout = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    mains: [...document.querySelectorAll('main')].filter((node) => node.getClientRects().length > 0).length,
  }));
  expect(layout.scrollWidth).toBeLessThanOrEqual(layout.width);
  expect(layout.mains).toBe(1);
  return layout;
}

for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 768, height: 1024 }]) {
  test(`catálogo real ${viewport.width}x${viewport.height}`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport);
    const errors = [];
    const requests = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('response', (response) => {
      if (response.url().includes('/api/')) requests.push({ url: response.url(), status: response.status() });
    });
    const start = Date.now();
    await page.goto('/catalogo');
    await expect(page.getByRole('status').filter({ hasText: '1080 productos' })).toBeVisible();
    await expect(page.locator('.catalogo__contenido li')).toHaveCount(24);
    await expect(page.getByLabel('Categoría').getByRole('option', { name: 'Categoria 00', exact: true })).toHaveCount(1);
    const usableMs = Date.now() - start;
    await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
    const layout = await checkLayout(page);
    await page.screenshot({ path: testInfo.outputPath('catalogo.png'), fullPage: true });
    const initialRequests = [...requests];
    expect(initialRequests.filter((r) => r.url.endsWith('/configuracion/'))).toHaveLength(1);
    expect(initialRequests.filter((r) => r.url.includes('/catalogo/filtros/'))).toHaveLength(0);
    const last = page.getByRole('button', { name: 'Página 45', exact: true });
    const lastResponse = page.waitForResponse((res) => new URL(res.url()).searchParams.get('page') === '45' && res.status() === 200);
    await last.focus();
    await page.keyboard.press('Enter');
    await lastResponse;
    await expect(last).toHaveAttribute('aria-current', 'page');
    await expect(page.locator('.catalogo__contenido li')).toHaveCount(24);
    const lastLayout = await checkLayout(page);
    await page.getByLabel('Categoría', { exact: true }).selectOption('Categoria 00');
    await expect(page.getByRole('status').filter({ hasText: '300 productos' })).toBeVisible();
    const filteredLayout = await checkLayout(page);
    await expect(page.getByRole('button', { name: 'Página 1', exact: true })).toHaveAttribute('aria-current', 'page');
    await page.getByLabel('capacidad gb', { exact: true }).selectOption('128');
    await expect(page.getByRole('status').filter({ hasText: '100 productos' })).toBeVisible();
    await page.getByLabel('capacidad gb', { exact: true }).selectOption('');
    await expect(page.getByRole('status').filter({ hasText: '300 productos' })).toBeVisible();
    await page.getByLabel('color', { exact: true }).selectOption('Verde');
    await expect(page.getByRole('status').filter({ hasText: '100 productos' })).toBeVisible();
    await page.getByLabel('color', { exact: true }).selectOption('');
    await expect(page.getByRole('status').filter({ hasText: '300 productos' })).toBeVisible();
    for (const order of ['precio-asc', 'precio-desc']) {
      const response = page.waitForResponse((res) => res.url().includes(`orden=${order}`) && res.status() === 200);
      await page.getByLabel('Ordenar por').selectOption(order);
      await response;
      await expect(page.locator('.catalogo__contenido li')).toHaveCount(24);
    }
    await page.locator('.catalogo__contenido li a').first().click();
    await expect(page).toHaveURL(/\/catalogo\/producto\//);
    expect(errors).toEqual([]);
    expect(requests.filter((r) => r.status >= 400)).toEqual([]);
    await testInfo.attach('observaciones', { body: JSON.stringify({ viewport, layout, lastLayout, filteredLayout, usableMs, initialRequests, requests, errors }, null, 2), contentType: 'application/json' });
  });
}

test('administrador edita precio y contacto; catálogo y pie reciben los cambios reales', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  const api = 'http://127.0.0.1:8000/api/';
  const login = await page.request.post(api + 'usuarios/token/', {
    data: { email: process.env.QA149_ADMIN_EMAIL, password: process.env.QA149_ADMIN_PASSWORD },
  });
  expect(login.ok()).toBeTruthy();
  const tokens = await login.json();
  const headers = { Authorization: `Bearer ${tokens.access}` };
  const productPath = api + 'catalogo/productos/000000000000000000000060/';
  const original = await (await page.request.get(productPath)).json();
  const originalConfig = await (await page.request.get(api + 'configuracion/negocio/', { headers })).json();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/');
  await page.getByRole('button', { name: 'Rechazar', exact: true }).click();
  await page.evaluate((value) => {
    localStorage.setItem('access_token', value.access);
    localStorage.setItem('refresh_token', value.refresh);
    localStorage.setItem('rol', 'ADMIN');
  }, tokens);
  try {
    await page.goto('/admin');
    await page.getByRole('button', { name: 'Inventario', exact: true }).click();
    await expect(page.getByText('Mostrando 1140 de 1140 producto(s)', { exact: true })).toBeVisible();
    await expect(page.getByLabel('Filtrar por Categoría').locator('option')).toHaveCount(13);
    await page.getByRole('button', { name: 'Editar Producto QA149 0095', exact: true }).click();
    await expect(page.getByLabel('Categoría', { exact: true }).locator('option')).toHaveCount(13);
    await page.getByLabel('Precio', { exact: true }).fill('20000');
    await page.getByLabel('Precio Oferta', { exact: true }).fill('');
    const saved = page.waitForResponse((res) => res.url() === productPath && res.request().method() === 'PUT' && res.status() === 200);
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: 'Guardar cambios del producto', exact: true }).click();
    await saved;
    await page.getByRole('button', { name: '✓ Finalizar', exact: true }).click();
    await expect(page.getByText('Mostrando 1140 de 1140 producto(s)', { exact: true })).toBeVisible();
    const persisted = await (await page.request.get(productPath)).json();
    expect(Number(persisted.variantes[0].precio)).toBe(20000);
    await page.getByRole('button', { name: 'Configuración', exact: true }).click();
    await page.getByLabel('Correo de contacto', { exact: true }).fill('contacto149@example.test');
    await page.getByRole('button', { name: 'Guardar contacto y redes', exact: true }).click();
    await expect(page.getByText('Datos de contacto guardados: ya se ven en tu tienda.', { exact: true })).toBeVisible();
    await expect(page.locator('footer').getByRole('link', { name: 'contacto149@example.test' })).toBeVisible();
    await page.getByRole('button', { name: /Ver mi tienda/ }).click();
    // La comprobación de visibilidad pública utiliza una sesión anónima.
    await page.evaluate(() => {
      for (const key of ['access_token', 'refresh_token', 'rol']) localStorage.removeItem(key);
    });
    await page.locator('header').getByRole('link', { name: 'Catálogo', exact: true }).click();
    await expect(page.locator('.catalogo__contenido li')).toHaveCount(24);
    const ordered = page.waitForResponse((res) => res.url().includes('orden=precio-desc') && res.status() === 200);
    await page.getByLabel('Ordenar por').selectOption('precio-desc');
    await ordered;
    await expect(page.locator('.catalogo__contenido li').first()).toContainText('Producto QA149 0095');
    await page.screenshot({ path: testInfo.outputPath('precio-editado-publico.png') });
    expect(errors).toEqual([]);
    await testInfo.attach('edicion-real', { body: JSON.stringify({ productId: original.id, price: persisted.variantes[0].precio, contactRefreshed: true, errors }), contentType: 'application/json' });
  } finally {
    expect((await page.request.patch(productPath, { headers,
      data: { variantes: original.variantes, atributos_globales: original.atributos_globales },
    })).ok()).toBeTruthy();
    expect((await page.request.patch(api + 'configuracion/negocio/', { headers,
      data: { correo_contacto: originalConfig.correo_contacto },
    })).ok()).toBeTruthy();
  }
});
