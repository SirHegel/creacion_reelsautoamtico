/* Prueba técnica 3 s. CLONE: agrupación → reorganización → estado/resultante.
   GSAP real, plugins locales y una timeline pausada dirigida por HyperFrames. */
document.fonts.ready.then(() => {
  if (!window.gsap || !window.MotionPathPlugin || !window.MorphSVGPlugin) {
    throw new Error('GSAP y sus plugins locales deben estar cargados');
  }
  gsap.registerPlugin(MotionPathPlugin, MorphSVGPlugin);
  const tl = gsap.timeline({paused: true});
  tl.addLabel('fuentes', 0).addLabel('transferencia', .65)
    .addLabel('agrupacion', 1.35).addLabel('resultado', 2.15);

  // Tres superficies independientes se agrupan y abren sus máscaras de datos.
  tl.fromTo('#source-a', {x: -230, y: 120, rotation: -17, scale: .74},
    {x: 0, y: 0, rotation: -6, scale: 1, duration: .32, ease: 'expo.out'}, .08);
  tl.fromTo('#source-b', {x: 220, y: -80, rotation: 18, scale: .7},
    {x: 0, y: 0, rotation: 7, scale: 1, duration: .34, ease: 'power3.out'}, .16);
  tl.fromTo('#source-c', {y: 100, rotation: -9, scale: .76},
    {y: 0, rotation: 0, scale: 1, duration: .30, ease: 'power2.out'}, .24);
  tl.fromTo('.source-data', {clipPath: 'inset(0% 100% 0% 0%)'},
    {clipPath: 'inset(0% 0% 0% 0%)', duration: .26, stagger: .075, ease: 'power3.out'}, .38);
  tl.fromTo('#processor', {scale: .72, opacity: 0, transformOrigin: '540px 1160px'},
    {scale: 1, opacity: 1, duration: .28, ease: 'power3.out'}, .50);

  // El trazo conecta las fuentes reales de la composición con su destino.
  ['a', 'b', 'c'].forEach((id, i) => {
    const path = document.querySelector('#route-' + id);
    const length = path.getTotalLength();
    tl.fromTo(path, {strokeDasharray: length, strokeDashoffset: length},
      {strokeDashoffset: 0, duration: .26, ease: 'power2.out'}, .53 + i * .055);
    tl.set('#packet-' + id, {opacity: 1}, .68 + i * .08);
    tl.to('#packet-' + id, {motionPath: {path, align: path, alignOrigin: [.5, .5]},
      duration: .60, ease: 'power2.inOut'}, .68 + i * .08);
    tl.to('#packet-' + id, {scale: 1.7, opacity: 0, duration: .12, ease: 'power2.in'}, 1.24 + i * .08);
  });
  // Las superficies reaccionan a la extracción y convergen en un solo sistema.
  tl.to('.source-name', {opacity: 0, duration: .14}, .91);
  tl.to('#source-a', {x: 260, y: 270, rotation: 12, scale: .16, opacity: 0,
    duration: .38, ease: 'power3.in'}, .96);
  tl.to('#source-b', {x: -270, y: 270, rotation: -12, scale: .16, opacity: 0,
    duration: .38, ease: 'expo.in'}, 1.03);
  tl.to('#source-c', {y: 470, scale: .16, opacity: 0, duration: .36, ease: 'power2.in'}, 1.10);
  tl.to('#routes', {opacity: 0, duration: .16}, 1.43);
  tl.to('#processor', {scale: 1.08, duration: .12, ease: 'power2.out'}, 1.30);
  tl.to('#processor', {scale: 1, duration: .14, ease: 'power3.inOut'}, 1.42);
  tl.to('#processing-label', {y: -25, opacity: 0, duration: .18, ease: 'power3.in'}, 1.43);

  // Una misma silueta cambia de sistema a documento; no reemplazo por fade.
  tl.to('#processor', {morphSVG: 'M315 720H655L765 830V1440H315Z',
    fill: '#f4f3ef', stroke: '#f4f3ef', duration: .53, ease: 'power3.inOut'}, 1.57);
  tl.fromTo('#fold', {clipPath: 'inset(0% 100% 0% 0%)'},
    {clipPath: 'inset(0% 0% 0% 0%)', duration: .24, ease: 'power3.out'}, 1.96);
  tl.fromTo('.result-line', {scaleX: 0, x: 90, transformOrigin: 'left center'},
    {scaleX: 1, x: 0, duration: .24, stagger: .045, ease: 'power3.out'}, 1.99);
  tl.to('#opening-title', {y: -32, opacity: 0, duration: .18, ease: 'power3.in'}, 1.74);
  tl.fromTo('#final-title', {clipPath: 'inset(0% 0% 100% 0%)', y: 32},
    {clipPath: 'inset(0% 0% 0% 0%)', y: 0, duration: .24, ease: 'expo.out'}, 2.03);
  // Cámara virtual: mantiene la identidad del objeto y remata sobre el resultado.
  tl.to('#world', {scale: 1.10, y: -45, x: 0, transformOrigin: '540px 1050px',
    duration: .24, ease: 'power3.out'}, 2.33);
  tl.to('#world', {scale: 1.05, y: -25, duration: .18, ease: 'power3.inOut'}, 2.62);

  window.__gsapEvidence = {version: gsap.version, motionPath: !!gsap.plugins.motionPath,
    morphSVG: !!gsap.plugins.morphSVG, composition: 'arquitectura-gsap', duration: 3,
    mecanismos: ['posicion','escala','mascara','trayectoria','morphing','camara'],
    fuentes: 3, tweens: tl.getChildren(true, true, false).length};
  window.__timelines = window.__timelines || {};
  window.__timelines['arquitectura-gsap'] = tl;
  window.renderReady = true;
});
