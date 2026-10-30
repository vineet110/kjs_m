'use client';
// A product picture for the home page cards (product range, recommended) that fades in once it has
// loaded, instead of popping in. Visible by default (server HTML, no JavaScript); only a picture still
// loading after the page starts is hidden, until it loads or fails (a failed one shows the browser's
// fallback). Fills its parent, which must be `relative` with a set size.
import Image from 'next/image';
import { useEffect, useRef, useState } from 'react';

export default function CardImage({ src, alt }: { src: string; alt: string }) {
  const img = useRef<HTMLImageElement>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    if (img.current && !img.current.complete) setPending(true);
  }, []);
  return (
    <Image
      ref={img}
      src={src}
      alt={alt}
      fill
      sizes="(max-width: 768px) 50vw, 25vw"
      onLoad={() => setPending(false)}
      onError={() => setPending(false)}
      className={`object-cover transition-[opacity,transform] duration-500 group-hover:scale-105 ${pending ? 'opacity-0' : 'opacity-100'}`}
    />
  );
}
