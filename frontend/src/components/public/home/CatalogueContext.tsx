'use client';
// The home page's product list, sent to the browser once and shared by the search, the category menu
// and the product range (instead of passing the full list to each of them).
import { createContext, useContext } from 'react';
import type { HomeProduct } from '@/lib/catalogue';

const Catalogue = createContext<HomeProduct[]>([]);

export function CatalogueProvider({ products, children }: { products: HomeProduct[]; children: React.ReactNode }) {
  return <Catalogue.Provider value={products}>{children}</Catalogue.Provider>;
}

export function useCatalogue(): HomeProduct[] {
  return useContext(Catalogue);
}
