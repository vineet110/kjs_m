// Screen 01: Home page (Header, Ticker, Best Sellers, Categories)
import OffersTicker from '@/components/public/OffersTicker';
import BestSellersSection from '@/components/public/BestSellersSection';
import CategoryGrid from '@/components/public/CategoryGrid';
import Header from '@/components/common/Header';

export default function HomePage() {
  return (
    <main className="min-h-screen bg-slate-50">
      <Header />
      <OffersTicker />
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-12">
        <section className="text-center space-y-4 py-6">
          <span className="text-xs uppercase tracking-widest font-bold text-blue-600 bg-blue-50 px-3 py-1 rounded-full">
            TRUSTED CO-MANUFACTURING PARTNER
          </span>
          <h1 className="text-4xl md:text-5xl font-extrabold text-slate-900 tracking-tight">
            Coffee, tea & confectionery,<br />made and packed by KJS
          </h1>
          <p className="text-slate-600 max-w-2xl mx-auto text-sm md:text-base">
            State-of-the-art manufacturing, automated packaging lines, and end-to-end quality assurance.
          </p>
        </section>

        <BestSellersSection />
        <CategoryGrid />
      </div>
    </main>
  );
}
