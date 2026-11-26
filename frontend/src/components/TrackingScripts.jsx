import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { isAdminRoute, isCookieConsentAccepted, suspendTracking } from '../hooks/useCookieConsent';

// RF-04.4: cada proveedor solo con su categoría aceptada: Google Analytics con 'analitica' y Meta Pixel con
// 'marketing'. En el panel de administración nunca se carga ninguno.
function TrackingScripts({ googleAnalyticsId, metaPixelId, analitica = false, marketing = false }) {
  const { pathname, search, key } = useLocation();
  const enAdmin = isAdminRoute(pathname);
  const allowedGa = analitica && !enAdmin;
  const allowedMeta = marketing && !enAdmin;
  const lastPageView = useRef({ ga: null, meta: null });

  // Google Analytics 4
  useEffect(() => {
    if (!allowedGa || !isCookieConsentAccepted('analitica')) {
      suspendTracking(['analitica']);
      return;
    }

    if (googleAnalyticsId) {
      window[`ga-disable-${googleAnalyticsId}`] = false;
      window.__ecodeGaInitialized ??= [];

      if (!window.__ecodeGaInitialized.includes(googleAnalyticsId)) {
        window.dataLayer = window.dataLayer || [];

        if (!window.gtag) {
          window.gtag = function () {
            window.dataLayer.push(arguments);
          };
          window.gtag('js', new Date());
        }

        if (!document.getElementById('ecode-google-analytics-script')) {
          const script = document.createElement('script');
          script.id = 'ecode-google-analytics-script';
          script.async = true;
          script.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(googleAnalyticsId)}`;
          script.onload = () => { window.__ecodeGaScriptLoaded = true; };
          document.head.appendChild(script);
        }

        window.gtag('config', googleAnalyticsId, {
          send_page_view: false,
        });

        window.__ecodeGaInitialized.push(googleAnalyticsId);
      }
    }
  }, [allowedGa, googleAnalyticsId]);

  // Meta Pixel
  useEffect(() => {
    if (!allowedMeta || !isCookieConsentAccepted('marketing')) {
      suspendTracking(['marketing']);
      return;
    }

    if (metaPixelId) {
      window.__ecodeMetaPixelInitialized ??= [];

      if (!window.__ecodeMetaPixelInitialized.includes(metaPixelId)) {
        if (!window.fbq) {
          const fbq = function () {
            if (fbq.callMethod) {
              fbq.callMethod.apply(fbq, arguments);
            } else {
              fbq.queue.push(arguments);
            }
          };

          fbq.push = fbq;
          fbq.loaded = true;
          fbq.version = '2.0';
          fbq.queue = [];
          window.fbq = fbq;
          window._fbq = fbq;
        }

        window.fbq('consent', 'grant');
        if (!document.getElementById('ecode-meta-pixel-script')) {
          const script = document.createElement('script');
          script.id = 'ecode-meta-pixel-script';
          script.async = true;
          script.src = 'https://connect.facebook.net/en_US/fbevents.js';
          document.head.appendChild(script);
        }

        window.fbq('init', metaPixelId);
        window.__ecodeMetaPixelInitialized.push(metaPixelId);
      } else {
        window.fbq('consent', 'grant');
      }
    }
  }, [allowedMeta, metaPixelId]);

  // Registrar visitas en la navegación entre páginas de React, en cada proveedor permitido.
  useEffect(() => {
    const navigation = `${key}:${pathname}${search}`;
    const gaVisit = `${googleAnalyticsId}:${navigation}`;
    const metaVisit = `${metaPixelId}:${navigation}`;

    if (
      allowedGa && isCookieConsentAccepted('analitica') &&
      googleAnalyticsId &&
      window.gtag &&
      window.__ecodeGaInitialized?.includes(googleAnalyticsId) &&
      lastPageView.current.ga !== gaVisit
    ) {
      window.gtag('event', 'page_view', {
        page_path: `${pathname}${search}`,
        page_location: window.location.href,
        send_to: googleAnalyticsId,
      });
      lastPageView.current.ga = gaVisit;
    }

    if (
      allowedMeta && isCookieConsentAccepted('marketing') &&
      metaPixelId &&
      window.fbq &&
      window.__ecodeMetaPixelInitialized?.includes(metaPixelId) &&
      lastPageView.current.meta !== metaVisit
    ) {
      window.fbq('track', 'PageView');
      lastPageView.current.meta = metaVisit;
    }
  }, [key, pathname, search, allowedGa, allowedMeta, googleAnalyticsId, metaPixelId]);

  return null;
}

export default TrackingScripts;
