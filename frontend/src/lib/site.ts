// Company facts and capability pages, taken from kjsindia.com (exported 23 Oct 2026).
// Source text: docs/research/source/kjsindia-site-text.md

export const SITE = {
  name: 'KJS India',
  tagline: 'Trusted Co-Manufacturing Partner',
  since: 2020,
  phone: '+91 97037 35666',
  whatsapp: 'https://wa.me/919703735666',
  email: 'contact@kjsindia.com',
  careers: 'hr@kjsindia.com',
  address: 'Plot No. 1 & 2, Phase-III, IDA Pashamylaram, Patancheru, Sangareddy, Hyderabad, Telangana 502307',
  trustedBy: ['Nestlé', 'Unilever', 'Mayora'],
  certifications: [
    { name: 'ISO 9001', img: '/images/kjs/brand/iso-9001.jpg' },
    { name: 'ISO 14001', img: '/images/kjs/brand/14001.jpg' },
    { name: 'FSSC 22000', img: '/images/kjs/brand/Fssc.jpg' },
    { name: 'Sodexo', img: '/images/kjs/brand/sudexo.jpg' },
  ],
};

export type Capability = {
  slug: string;
  title: string;
  summary: string;
  video: string;
  intro: string[];
  sections: { heading: string; items: string[] }[];
};

export const CAPABILITIES: Capability[] = [
  {
    slug: 'stick-pack-factory',
    title: 'Stick Pack Factory',
    summary: 'Accurate single-serve fills from 0.9 g to 3 g on high-speed lines.',
    video: '/images/kjs/video/innerpage.mp4',
    intro: [
      'KJS India is a stick-pack specialist trusted by companies looking to scale their single-serve formats. We offer highly accurate fills from 0.9 g to 3 g, fully customisable to your formulation.',
      'Whether you are launching a new SKU or expanding your single-serve portfolio, we provide the reliability, speed and precision brands expect from a world-class co-manufacturer.',
    ],
    sections: [
      { heading: 'What you get', items: ['Fills from 0.9 g to 3 g', 'High-speed packaging lines', 'Consistent sealing and clean cuts', 'Premium output at competitive volumes'] },
    ],
  },
  {
    slug: 'processing',
    title: 'Processing: Blending & Ball Milling',
    summary: 'Six industrial ribbon blenders and ball milling for confectionery.',
    video: '/images/kjs/video/services.mp4',
    intro: [
      'Ingredient blending is one of the most critical steps in producing high-quality food products. KJS ensures precision, consistency and safety across every batch, for dry powder blending and custom formulations.',
    ],
    sections: [
      { heading: 'Ribbon blending', items: ['Six full-scale industrial ribbon blenders', 'Counter-directional flow for superior homogeneity', 'Blending times of 10–20 minutes', 'Powders, premixes, nutraceutical blends, seasoning mixes and more'] },
      { heading: 'Confectionery ball milling', items: ['Precise particle-size reduction', 'Smooth texture development', 'Consistent mass for chocolates, cocoa-based products and speciality bases'] },
    ],
  },
  {
    slug: 'packaging',
    title: 'Packaging',
    summary: 'Pouches, cartons, bag-in-box and master shippers, customised to your spec.',
    video: '/images/kjs/video/package.mp4',
    intro: [
      'Packaging keeps consumers safe and draws them to your brand. Our standard capabilities cover most food packaging needs, and our custom services let us build packaging specific to your product.',
    ],
    sections: [
      { heading: 'Formats', items: ['Vertical form fill & seal pouch', 'Horizontal form fill & seal pouch', 'Pouch in carton', 'Direct fill carton', 'Master shipper packaging', 'Bag in box'] },
    ],
  },
  {
    slug: 'warehousing',
    title: 'Warehousing',
    summary: '15 days free warehousing for contract manufacturing customers.',
    video: '/images/kjs/video/innerpage.mp4',
    intro: [
      'Food warehousing is the link between processing and distribution. We control product flow and conditions closely: pest control, sanitation and trained personnel.',
    ],
    sections: [
      { heading: 'Benefits', items: ['15 days free warehousing on inbound and outbound shipments', 'Separate areas for raw ingredients, packaging and finished goods', 'Dedicated shipping personnel', 'Allergen segregation', 'Designated, labelled locations', 'Cold storage on request'] },
    ],
  },
  {
    slug: 'quality-and-testing',
    title: 'Quality & Testing',
    summary: 'Audit-ready plant with HACCP, metal detection and in-house testing.',
    video: '/images/kjs/video/quality.mp4',
    intro: [
      'Quality is at the core of our culture. Our facility is always audit-ready, even for unannounced audits, and we ace plant audits by the most stringent food auditors.',
      'We create a processing profile for every project and keep you informed on runs, product loss, finished quantities, delivery schedules and packaging inventory.',
    ],
    sections: [
      { heading: 'Our approach', items: ['HACCP plans with screens, magnets and metal detection', 'Allergen control and micro-contamination monitoring', 'Dust collection on every line', 'Sanitation and preventive maintenance per machine', 'Visitor and subcontractor security protocols'] },
      { heading: 'Testing', items: ['Sieve testing: particle size distribution', 'Bulk density', 'Moisture', 'pH', 'External micro testing'] },
    ],
  },
];
