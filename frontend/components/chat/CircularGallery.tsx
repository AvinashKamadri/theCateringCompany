/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useRef } from 'react';
import './CircularGallery.css';

export interface GalleryItem {
  image: string;
  text: string;
}

interface CircularGalleryProps {
  items?: GalleryItem[];
  bend?: number;
  textColor?: string;
  borderRadius?: number;
  font?: string;
  scrollSpeed?: number;
  scrollEase?: number;
}

function debounce(func: (...args: any[]) => void, wait: number) {
  let timeout: ReturnType<typeof setTimeout>;
  return function (this: any, ...args: any[]) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

function lerp(p1: number, p2: number, t: number) {
  return p1 + (p2 - p1) * t;
}

function createTextTexture(OGL: any, gl: any, text: string, font = 'bold 30px monospace', color = 'white') {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d')!;
  ctx.font = font;
  const metrics = ctx.measureText(text);
  const tw = Math.ceil(metrics.width) + 20;
  const th = Math.ceil(parseInt(font, 10) * 1.2) + 20;
  canvas.width = tw;
  canvas.height = th;
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.textBaseline = 'middle';
  ctx.textAlign = 'center';
  ctx.clearRect(0, 0, tw, th);
  ctx.fillText(text, tw / 2, th / 2);
  const texture = new OGL.Texture(gl, { generateMipmaps: false });
  texture.image = canvas;
  return { texture, width: tw, height: th };
}

class Media {
  extra = 0; x = 0; width = 0; widthTotal = 0; speed = 0; padding = 0;
  isBefore = false; isAfter = false;
  plane: any; program: any; OGL: any;
  gl: any; geometry: any; image: string; index: number; length: number;
  renderer: any; scene: any; screen: any; text: string; viewport: any;
  bend: number; textColor: string; borderRadius: number; font: string;

  constructor({ OGL, geometry, gl, image, index, length, renderer, scene, screen, text, viewport, bend, textColor, borderRadius, font }: any) {
    this.OGL = OGL;
    this.geometry = geometry; this.gl = gl; this.image = image;
    this.index = index; this.length = length; this.renderer = renderer;
    this.scene = scene; this.screen = screen; this.text = text;
    this.viewport = viewport; this.bend = bend; this.textColor = textColor;
    this.borderRadius = borderRadius; this.font = font;
    this.createShader();
    this.createMesh();
    this.createTitle();
    this.onResize();
  }

  createShader() {
    const { Texture, Program } = this.OGL;
    const texture = new Texture(this.gl, { generateMipmaps: true });
    this.program = new Program(this.gl, {
      depthTest: false, depthWrite: false,
      vertex: `
        precision highp float;
        attribute vec3 position; attribute vec2 uv;
        uniform mat4 modelViewMatrix; uniform mat4 projectionMatrix;
        varying vec2 vUv;
        void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }
      `,
      fragment: `
        precision highp float;
        uniform vec2 uImageSizes; uniform vec2 uPlaneSizes;
        uniform sampler2D tMap; uniform float uBorderRadius;
        varying vec2 vUv;
        float roundedBoxSDF(vec2 p, vec2 b, float r) {
          vec2 d = abs(p) - b;
          return length(max(d, vec2(0.0))) + min(max(d.x, d.y), 0.0) - r;
        }
        void main() {
          vec2 ratio = vec2(
            min((uPlaneSizes.x / uPlaneSizes.y) / (uImageSizes.x / uImageSizes.y), 1.0),
            min((uPlaneSizes.y / uPlaneSizes.x) / (uImageSizes.y / uImageSizes.x), 1.0)
          );
          vec2 uv = vec2(vUv.x * ratio.x + (1.0 - ratio.x) * 0.5, vUv.y * ratio.y + (1.0 - ratio.y) * 0.5);
          vec4 color = texture2D(tMap, uv);
          float d = roundedBoxSDF(vUv - 0.5, vec2(0.5 - uBorderRadius), uBorderRadius);
          float alpha = 1.0 - smoothstep(-0.002, 0.002, d);
          gl_FragColor = vec4(color.rgb, alpha);
        }
      `,
      uniforms: {
        tMap: { value: texture },
        uPlaneSizes: { value: [0, 0] },
        uImageSizes: { value: [0, 0] },
        uSpeed: { value: 0 },
        uTime: { value: 100 * Math.random() },
        uBorderRadius: { value: this.borderRadius },
      },
      transparent: true,
    });
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = this.image;
    img.onload = () => {
      texture.image = img;
      this.program.uniforms.uImageSizes.value = [img.naturalWidth, img.naturalHeight];
    };
  }

  createMesh() {
    const { Mesh } = this.OGL;
    this.plane = new Mesh(this.gl, { geometry: this.geometry, program: this.program });
    this.plane.setParent(this.scene);
  }

  createTitle() {
    const { Program, Plane, Mesh } = this.OGL;
    const { texture, width, height } = createTextTexture(this.OGL, this.gl, this.text, this.font, this.textColor);
    const geom = new Plane(this.gl);
    const prog = new Program(this.gl, {
      vertex: `attribute vec3 position; attribute vec2 uv; uniform mat4 modelViewMatrix; uniform mat4 projectionMatrix; varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragment: `precision highp float; uniform sampler2D tMap; varying vec2 vUv; void main() { vec4 c = texture2D(tMap, vUv); if (c.a < 0.1) discard; gl_FragColor = c; }`,
      uniforms: { tMap: { value: texture } },
      transparent: true,
    });
    const mesh = new Mesh(this.gl, { geometry: geom, program: prog });
    const aspect = width / height;
    const textHeight = this.plane.scale.y * 0.15;
    mesh.scale.set(textHeight * aspect, textHeight, 1);
    mesh.position.y = -this.plane.scale.y * 0.5 - textHeight * 0.5 - 0.05;
    mesh.setParent(this.plane);
  }

  update(scroll: any, direction: string) {
    this.plane.position.x = this.x - scroll.current - this.extra;
    const x = this.plane.position.x;
    const H = this.viewport.width / 2;
    if (this.bend === 0) {
      this.plane.position.y = 0;
      this.plane.rotation.z = 0;
    } else {
      const B_abs = Math.abs(this.bend);
      const R = (H * H + B_abs * B_abs) / (2 * B_abs);
      const effectiveX = Math.min(Math.abs(x), H);
      const arc = R - Math.sqrt(R * R - effectiveX * effectiveX);
      if (this.bend > 0) { this.plane.position.y = -arc; this.plane.rotation.z = -Math.sign(x) * Math.asin(effectiveX / R); }
      else { this.plane.position.y = arc; this.plane.rotation.z = Math.sign(x) * Math.asin(effectiveX / R); }
    }
    this.speed = scroll.current - scroll.last;
    this.program.uniforms.uTime.value += 0.04;
    this.program.uniforms.uSpeed.value = this.speed;
    const planeOffset = this.plane.scale.x / 2;
    const viewportOffset = this.viewport.width / 2;
    this.isBefore = this.plane.position.x + planeOffset < -viewportOffset;
    this.isAfter = this.plane.position.x - planeOffset > viewportOffset;
    if (direction === 'right' && this.isBefore) { this.extra -= this.widthTotal; this.isBefore = this.isAfter = false; }
    if (direction === 'left' && this.isAfter) { this.extra += this.widthTotal; this.isBefore = this.isAfter = false; }
  }

  onResize({ screen, viewport }: any = {}) {
    if (screen) this.screen = screen;
    if (viewport) this.viewport = viewport;
    const scale = this.screen.height / 1500;
    this.plane.scale.y = (this.viewport.height * (900 * scale)) / this.screen.height;
    this.plane.scale.x = (this.viewport.width * (700 * scale)) / this.screen.width;
    this.program.uniforms.uPlaneSizes.value = [this.plane.scale.x, this.plane.scale.y];
    this.padding = 2;
    this.width = this.plane.scale.x + this.padding;
    this.widthTotal = this.width * this.length;
    this.x = this.width * this.index;
  }
}

class App {
  container: HTMLElement;
  scrollSpeed: number;
  scroll: { ease: number; current: number; target: number; last: number; position?: number };
  onCheckDebounce: any;
  renderer: any; gl: any; camera: any; scene: any; planeGeometry: any;
  medias: Media[] = []; screen: any; viewport: any; raf = 0;
  isDown = false; start = 0;
  boundOnResize: any; boundOnWheel: any; boundOnTouchDown: any;
  boundOnTouchMove: any; boundOnTouchUp: any;

  constructor(container: HTMLElement, {
    items = [], bend = 3, textColor = '#ffffff', borderRadius = 0,
    font = 'bold 30px Figtree', scrollSpeed = 2, scrollEase = 0.05,
  }: { items?: GalleryItem[]; bend?: number; textColor?: string; borderRadius?: number; font?: string; scrollSpeed?: number; scrollEase?: number } = {}) {
    this.container = container;
    this.scrollSpeed = scrollSpeed;
    this.scroll = { ease: scrollEase, current: 0, target: 0, last: 0 };
    this.onCheckDebounce = debounce(this.onCheck.bind(this), 200);
    this._init({ items, bend, textColor, borderRadius, font });
  }

  async _init({ items, bend, textColor, borderRadius, font }: any) {
    const OGL = await import('ogl');
    const { Renderer, Camera, Transform, Plane } = OGL;
    this.renderer = new Renderer({ alpha: true, antialias: true, dpr: Math.min(window.devicePixelRatio || 1, 2) });
    this.gl = this.renderer.gl;
    this.gl.clearColor(0, 0, 0, 0);
    this.container.appendChild(this.gl.canvas);

    this.camera = new Camera(this.gl);
    this.camera.fov = 45;
    this.camera.position.z = 20;

    this.scene = new Transform();
    this.onResize();

    this.planeGeometry = new Plane(this.gl, { heightSegments: 50, widthSegments: 100 });
    this._createMedias({ OGL, items, bend, textColor, borderRadius, font });
    this.update();
    this._addEventListeners();
  }

  _createMedias({ OGL, items, bend, textColor, borderRadius, font }: any) {
    const defaultItems = [
      { image: 'https://picsum.photos/seed/1/800/600?grayscale', text: 'Item 1' },
      { image: 'https://picsum.photos/seed/2/800/600?grayscale', text: 'Item 2' },
    ];
    const list: GalleryItem[] = items?.length ? items : defaultItems;
    const all = list.concat(list);
    this.medias = all.map((data, i) => new Media({
      OGL, geometry: this.planeGeometry, gl: this.gl, image: data.image,
      index: i, length: all.length, renderer: this.renderer,
      scene: this.scene, screen: this.screen, text: data.text,
      viewport: this.viewport, bend, textColor, borderRadius, font,
    }));
  }

  onCheck() {
    if (!this.medias[0]) return;
    const w = this.medias[0].width;
    const idx = Math.round(Math.abs(this.scroll.target) / w);
    const item = w * idx;
    this.scroll.target = this.scroll.target < 0 ? -item : item;
  }

  onResize() {
    this.screen = { width: this.container.clientWidth, height: this.container.clientHeight };
    if (this.renderer) {
      this.renderer.setSize(this.screen.width, this.screen.height);
      this.camera.perspective({ aspect: this.screen.width / this.screen.height });
      const fov = (this.camera.fov * Math.PI) / 180;
      const h = 2 * Math.tan(fov / 2) * this.camera.position.z;
      this.viewport = { width: h * this.camera.aspect, height: h };
    }
    this.medias?.forEach((m) => m.onResize({ screen: this.screen, viewport: this.viewport }));
  }

  onTouchDown(e: any) {
    this.isDown = true;
    this.scroll.position = this.scroll.current;
    this.start = e.touches ? e.touches[0].clientX : e.clientX;
  }
  onTouchMove(e: any) {
    if (!this.isDown) return;
    const x = e.touches ? e.touches[0].clientX : e.clientX;
    this.scroll.target = (this.scroll.position ?? 0) + (this.start - x) * this.scrollSpeed * 0.025;
  }
  onTouchUp() { this.isDown = false; this.onCheck(); }
  onWheel(e: any) {
    const d = e.deltaY || e.wheelDelta || e.detail;
    this.scroll.target += (d > 0 ? this.scrollSpeed : -this.scrollSpeed) * 0.2;
    this.onCheckDebounce();
  }

  update() {
    this.scroll.current = lerp(this.scroll.current, this.scroll.target, this.scroll.ease);
    const dir = this.scroll.current > this.scroll.last ? 'right' : 'left';
    this.medias?.forEach((m) => m.update(this.scroll, dir));
    this.renderer?.render({ scene: this.scene, camera: this.camera });
    this.scroll.last = this.scroll.current;
    this.raf = requestAnimationFrame(this.update.bind(this));
  }

  _addEventListeners() {
    this.boundOnResize = this.onResize.bind(this);
    this.boundOnWheel = this.onWheel.bind(this);
    this.boundOnTouchDown = this.onTouchDown.bind(this);
    this.boundOnTouchMove = this.onTouchMove.bind(this);
    this.boundOnTouchUp = this.onTouchUp.bind(this);
    window.addEventListener('resize', this.boundOnResize);
    window.addEventListener('wheel', this.boundOnWheel);
    window.addEventListener('mousedown', this.boundOnTouchDown);
    window.addEventListener('mousemove', this.boundOnTouchMove);
    window.addEventListener('mouseup', this.boundOnTouchUp);
    window.addEventListener('touchstart', this.boundOnTouchDown);
    window.addEventListener('touchmove', this.boundOnTouchMove);
    window.addEventListener('touchend', this.boundOnTouchUp);
  }

  destroy() {
    cancelAnimationFrame(this.raf);
    window.removeEventListener('resize', this.boundOnResize);
    window.removeEventListener('wheel', this.boundOnWheel);
    window.removeEventListener('mousedown', this.boundOnTouchDown);
    window.removeEventListener('mousemove', this.boundOnTouchMove);
    window.removeEventListener('mouseup', this.boundOnTouchUp);
    window.removeEventListener('touchstart', this.boundOnTouchDown);
    window.removeEventListener('touchmove', this.boundOnTouchMove);
    window.removeEventListener('touchend', this.boundOnTouchUp);
    if (this.gl?.canvas?.parentNode) this.gl.canvas.parentNode.removeChild(this.gl.canvas);
  }
}

export default function CircularGallery({
  items, bend = 0, textColor = '#ffffff',
  borderRadius = 0.1, font = 'bold 30px Figtree',
  scrollSpeed = 2.5, scrollEase = 0.15,
}: CircularGalleryProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const app = new App(containerRef.current, { items, bend, textColor, borderRadius, font, scrollSpeed, scrollEase });
    return () => app.destroy();
  }, [items, bend, textColor, borderRadius, font, scrollSpeed, scrollEase]);

  return <div className="circular-gallery" ref={containerRef} />;
}
