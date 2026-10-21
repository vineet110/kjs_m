import { getRequestConfig } from 'next-intl/server';
import en from '../../messages/en.json';
import hi from '../../messages/hi.json';

const messages = { en, hi };

export default getRequestConfig(async ({ requestLocale }) => {
  const requestedLocale = await requestLocale;
  const locale = requestedLocale === 'hi' ? 'hi' : 'en';

  return {
    locale,
    messages: messages[locale],
  };
});