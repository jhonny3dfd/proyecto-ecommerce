import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Lo que guarda el hook: la elección por categoría y la fecha (vence a los 12 meses)
const decision = (analitica, marketing, fecha = new Date()) => JSON.stringify({ analitica, marketing, fecha: fecha.toISOString() });
const leerDecision = (clave) => JSON.parse(localStorage.getItem(clave));
const haceDias = (dias) => new Date(Date.now() - dias * 24 * 60 * 60 * 1000);

describe('useCookieConsent', () => {
  let useCookieConsentModule;
    let useCookieConsent;
    let COOKIE_CONSENT_KEY;
    let isAdminRoute;
    let isCookieConsentAccepted;
    let suspendTracking;

    beforeEach(async () => {
        vi.restoreAllMocks();
        localStorage.clear();

        delete window.__ecodeGaInitialized;
        delete window.__ecodeGaScriptLoaded;
        delete window.__ecodeMetaPixelInitialized;
        delete window.dataLayer;
        delete window.fbq;

        vi.resetModules();

        useCookieConsentModule = await import('../hooks/useCookieConsent');

        useCookieConsent = useCookieConsentModule.default;
        COOKIE_CONSENT_KEY = useCookieConsentModule.COOKIE_CONSENT_KEY;
        isAdminRoute = useCookieConsentModule.isAdminRoute;
        isCookieConsentAccepted = useCookieConsentModule.isCookieConsentAccepted;
        suspendTracking = useCookieConsentModule.suspendTracking;
    });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  describe('estado inicial y almacenamiento', () => {
    it('muestra el banner cuando no existe una decisión guardada', () => {
      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
      expect(result.current.storageError).toBe('');
    });

    it('reconoce una aceptación guardada', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, decision(true, true));

      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('accepted');
      expect(result.current.preferences).toEqual({ analitica: true, marketing: true });
      expect(result.current.isBannerOpen).toBe(false);
      expect(isCookieConsentAccepted()).toBe(true);
    });

    it('vuelve a guardar una aceptación existente', () => {
      const guardada = decision(true, false);
      localStorage.setItem(COOKIE_CONSENT_KEY, guardada);
      const setItem = vi.spyOn(Storage.prototype, 'setItem');

      renderHook(() => useCookieConsent());

      expect(setItem).toHaveBeenCalledWith(COOKIE_CONSENT_KEY, guardada);
    });

    it('vuelve a preguntar una aceptación del formato anterior: no permitía elegir por categoría', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted');

      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
      expect(isCookieConsentAccepted()).toBe(false);
    });

    it('respeta un rechazo del formato anterior y desde ahí corre su vigencia', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');

      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('rejected');
      expect(leerDecision(COOKIE_CONSENT_KEY)).toEqual(expect.objectContaining({ analitica: false, marketing: false }));
      expect(Date.now() - Date.parse(leerDecision(COOKIE_CONSENT_KEY).fecha)).toBeLessThan(5000);
    });

    it('una decisión de hace 364 días sigue vigente', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, decision(true, true, haceDias(364)));

      expect(renderHook(() => useCookieConsent()).result.current.consent).toBe('accepted');
    });

    it('la decisión vence a los 12 meses y se vuelve a preguntar', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, decision(true, true, haceDias(366)));

      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
      expect(isCookieConsentAccepted()).toBe(false);
    });

    it.each([
      ['sin fecha', JSON.stringify({ analitica: true, marketing: true })],
      ['con una categoría que no es booleana', JSON.stringify({ analitica: 'si', marketing: true, fecha: new Date().toISOString() })],
      ['con el JSON roto', '{analitica'],
    ])('trata una decisión %s como pendiente', (_, valor) => {
      localStorage.setItem(COOKIE_CONSENT_KEY, valor);

      expect(renderHook(() => useCookieConsent()).result.current.consent).toBe('pending');
    });

    it('reconoce un rechazo guardado', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');

      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('rejected');
      expect(result.current.isBannerOpen).toBe(false);
      expect(isCookieConsentAccepted()).toBe(false);
    });

    it.each(['', 'invalid', 'true', 'pending'])(
      'trata el valor guardado "%s" como pendiente',
      (value) => {
        localStorage.setItem(COOKIE_CONSENT_KEY, value);

        const { result } = renderHook(() => useCookieConsent());

        expect(result.current.consent).toBe('pending');
        expect(result.current.isBannerOpen).toBe(true);
      },
    );

    it('bloquea el seguimiento si falla la lectura del almacenamiento', () => {
      vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('Storage no disponible');
      });

      const { result } = renderHook(() => useCookieConsent());

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
      expect(result.current.storageError).toContain(
        'No pudimos acceder a tus preferencias',
      );
      expect(isCookieConsentAccepted()).toBe(false);
    });
  });

  describe('acciones del usuario', () => {
    it('acepta las cookies y guarda la decisión', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.acceptCookies();
      });

      expect(result.current.consent).toBe('accepted');
      expect(result.current.isBannerOpen).toBe(false);
      expect(leerDecision(COOKIE_CONSENT_KEY)).toEqual(expect.objectContaining({ analitica: true, marketing: true }));
      expect(isCookieConsentAccepted()).toBe(true);
    });

    it('acepta solo las categorías elegidas', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.savePreferences({ analitica: true, marketing: false, otra: true });
      });

      expect(result.current.consent).toBe('custom');
      expect(result.current.preferences).toEqual({ analitica: true, marketing: false });
      expect(leerDecision(COOKIE_CONSENT_KEY)).toEqual(expect.objectContaining({ analitica: true, marketing: false }));
      expect(leerDecision(COOKIE_CONSENT_KEY)).not.toHaveProperty('otra');
      expect(isCookieConsentAccepted('analitica')).toBe(true);
      expect(isCookieConsentAccepted('marketing')).toBe(false);
    });

    it('retirar solo la publicidad quita el Pixel, deja Analytics y recarga', () => {
      const reload = vi.fn();
      vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload });
      localStorage.setItem(COOKIE_CONSENT_KEY, decision(true, true));
      for (const id of ['ecode-google-analytics-script', 'ecode-meta-pixel-script']) {
        const script = document.createElement('script');
        script.id = id;
        document.head.appendChild(script);
      }
      window.__ecodeMetaPixelInitialized = ['123'];
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.savePreferences({ analitica: true, marketing: false });
      });

      expect(document.getElementById('ecode-meta-pixel-script')).toBeNull();
      expect(document.getElementById('ecode-google-analytics-script')).not.toBeNull();
      expect(reload).toHaveBeenCalledTimes(1);
      document.getElementById('ecode-google-analytics-script').remove();
    });

    it('rechaza las cookies y guarda la decisión', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.rejectCookies();
      });

      expect(result.current.consent).toBe('rejected');
      expect(result.current.isBannerOpen).toBe(false);
      expect(leerDecision(COOKIE_CONSENT_KEY)).toEqual(expect.objectContaining({ analitica: false, marketing: false }));
      expect(isCookieConsentAccepted()).toBe(false);
    });

    it('abre nuevamente las preferencias', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.openPreferences();
      });

      expect(result.current.isBannerOpen).toBe(true);
    });

    it('cierra las preferencias cuando ya existe una decisión', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.openPreferences();
      });

      act(() => {
        result.current.closePreferences();
      });

      expect(result.current.isBannerOpen).toBe(false);
    });

    it('no permite cerrar el banner si la decisión sigue pendiente', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.closePreferences();
      });

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
    });

    it('mantiene pendiente la aceptación si no se puede guardar', () => {
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('Storage no disponible');
      });

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.acceptCookies();
      });

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
      expect(result.current.storageError).toContain(
        'No pudimos guardar tu elección',
      );
      expect(isCookieConsentAccepted()).toBe(false);
    });

    it('muestra el error si falla el guardado del rechazo', () => {
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('Storage no disponible');
      });

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.rejectCookies();
      });

      expect(result.current.consent).toBe('rejected');
      expect(result.current.isBannerOpen).toBe(true);
      expect(result.current.storageError).toContain(
        'No pudimos guardar tu elección',
      );
    });

    it('detecta que el almacenamiento no guardó la decisión solicitada', () => {
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});
      vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.acceptCookies();
      });

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
      expect(result.current.storageError).toContain(
        'No pudimos guardar tu elección',
      );
    });
  });

  describe('rutas de administración', () => {
    it.each([
      '/admin',
      '/ADMIN',
      '/admin/',
      '/admin/productos',
      '/%61dmin',
    ])('identifica la ruta administrativa %s', (pathname) => {
      expect(isAdminRoute(pathname)).toBe(true);
    });

    it.each([
      '/',
      '/catalogo',
      '/administracion',
      '/admin-productos',
      '/producto/admin',
    ])('no identifica %s como ruta administrativa', (pathname) => {
      expect(isAdminRoute(pathname)).toBe(false);
    });

    it('tolera rutas con codificación incorrecta', () => {
      expect(isAdminRoute('/%E0%A4%A')).toBe(false);
    });
  });

  describe('suspensión del seguimiento', () => {
    it('desactiva Google Analytics para los identificadores inicializados', () => {
      window.__ecodeGaInitialized = ['G-TEST1', 'G-TEST2'];

      suspendTracking();

      expect(window['ga-disable-G-TEST1']).toBe(true);
      expect(window['ga-disable-G-TEST2']).toBe(true);
    });

    it('elimina eventos pendientes de dataLayer si el script no se ha cargado', () => {
      window.dataLayer = [
        ['js', new Date()],
        ['config', 'G-TEST'],
        ['event', 'page_view'],
        ['event', 'purchase'],
      ];
      window.__ecodeGaScriptLoaded = false;

      suspendTracking();

      expect(window.dataLayer).toHaveLength(2);
      expect(window.dataLayer.map((command) => command[0])).toEqual([
        'js',
        'config',
      ]);
    });

    it('conserva dataLayer cuando Google Analytics ya cargó su script', () => {
      window.dataLayer = [
        ['config', 'G-TEST'],
        ['event', 'page_view'],
      ];
      window.__ecodeGaScriptLoaded = true;

      suspendTracking();

      expect(window.dataLayer).toHaveLength(2);
    });

    it('revoca el consentimiento de Meta Pixel si la librería ya está activa', () => {
      window.fbq = vi.fn();
      window.fbq.callMethod = vi.fn();

      suspendTracking();

      expect(window.fbq).toHaveBeenCalledWith('consent', 'revoke');
    });

    it('prepara la revocación en la cola de Meta Pixel si está cargando', () => {
      window.fbq = vi.fn();
      window.fbq.queue = [
        ['init', 'PIXEL-1'],
        ['track', 'PageView'],
        ['trackCustom', 'Accion'],
        ['consent', 'grant'],
        ['customCommand', 'dato'],
      ];

      suspendTracking();

      expect(window.fbq.queue).toEqual([
        ['consent', 'revoke'],
        ['init', 'PIXEL-1'],
        ['customCommand', 'dato'],
      ]);
    });
  });

  describe('sincronización entre pestañas', () => {
    it('actualiza el consentimiento cuando cambia el almacenamiento', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');

        window.dispatchEvent(
          new StorageEvent('storage', {
            key: COOKIE_CONSENT_KEY,
            storageArea: localStorage,
          }),
        );
      });

      expect(result.current.consent).toBe('rejected');
      expect(result.current.isBannerOpen).toBe(false);
    });

    it('ignora cambios de otras claves de almacenamiento', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');

        window.dispatchEvent(
          new StorageEvent('storage', {
            key: 'otra_clave',
            storageArea: localStorage,
          }),
        );
      });

      expect(result.current.consent).toBe('pending');
    });

    it('abre el banner si el consentimiento externo vuelve a pendiente', () => {
      localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted');

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        localStorage.setItem(COOKIE_CONSENT_KEY, 'pending');

        window.dispatchEvent(
          new StorageEvent('storage', {
            key: COOKIE_CONSENT_KEY,
            storageArea: localStorage,
          }),
        );
      });

      expect(result.current.consent).toBe('pending');
      expect(result.current.isBannerOpen).toBe(true);
    });

    it('sincroniza el estado cuando la página vuelve a mostrarse', () => {
      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        localStorage.setItem(COOKIE_CONSENT_KEY, 'rejected');
        window.dispatchEvent(new Event('pageshow'));
      });

      expect(result.current.consent).toBe('rejected');
    });
  });

  describe('limpieza de scripts de seguimiento', () => {
    it('elimina los scripts de Google Analytics y Meta Pixel al rechazar', () => {
      const googleScript = document.createElement('script');
      googleScript.id = 'ecode-google-analytics-script';
      document.body.appendChild(googleScript);

      const metaScript = document.createElement('script');
      metaScript.id = 'ecode-meta-pixel-script';
      document.body.appendChild(metaScript);

      const { result } = renderHook(() => useCookieConsent());

      act(() => {
        result.current.rejectCookies();
      });

      expect(
        document.getElementById('ecode-google-analytics-script'),
      ).toBeNull();
      expect(
        document.getElementById('ecode-meta-pixel-script'),
      ).toBeNull();
    });
  });
});
