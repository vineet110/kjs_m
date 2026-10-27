import { getRequestConfig } from 'next-intl/server';
import en from '../../messages/en.json';

// English only at launch (backlog D2). To add a language: messages/<code>.json + proxy.ts locales.
export default getRequestConfig(async () => ({
  locale: 'en',
  messages: en,
}));
