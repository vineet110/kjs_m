# KJS India Platform: Plan and Progress

A simple version of our project plan for the KJS team.

Last updated: 30 Oct 2026.



---------------------------------------------------------------------------------------------------

## 1. What we are building

One website with three parts:

1. Public website

   B2B buyers (retailers, distributors, importers, brands wanting private label) browse our products, ask for
   price sheets and samples, and chat with Koko, our AI assistant. Every enquiry is saved as a lead.


2. Employee portal

   Staff mark attendance, see their tasks and leads, and work on order boards.


3. Admin console

   The admin approves staff, assigns work, tracks orders and deadlines, and sees reports built from real data.



---------------------------------------------------------------------------------------------------

## 2. Key dates

1. Coding started: Mon 26 Oct 2026 (planned). All features were ready early, on 24 Oct.

2. Website scope frozen: Fri 6 Nov 2026

3. Go-live: Fri 11 Dec 2026

4. Latest acceptable go-live: Fri 18 Dec 2026



---------------------------------------------------------------------------------------------------

## 3. The plan

1. 26 Oct to 7 Nov: build everything for launch (website, employee portal, admin console).

   ✅ Done. All features built and tested on a laptop (24 Oct).


2. From 9 Nov: KJS sends real data (products, staff, holidays, FAQs). We load it and adjust.

   ⬜ Waiting on KJS.


3. November: production setup (KJS server, web address, email, file storage, backups).

   🟨 The parts that don't need the server are ready and tested (25 Oct). The rest needs server access and an IT contact.


4. Early December: testing with the KJS team, fixes.

   ⬜


5. Fri 11 Dec: go-live 🚀

   ⬜


6. 14 to 18 Dec: spare week and first-week support.


7. 2027 (Stage 2): buyer database, outreach emails, quotes, partner dashboard, more languages.


Status marks: ✅ done, 🟨 in progress, ⬜ not started, ⚠️ at risk



---------------------------------------------------------------------------------------------------

## 4. Decisions made

1. Website technology: Next.js (best for Google search ranking).

2. Languages: English at launch; other languages added later.

3. User roles: Admin and Employee (no Manager role).

4. Reports: built-in charts from real data at launch.

5. Database and hosting: free cloud database during development; moved to the KJS server later.

6. Images and files: Cloudflare storage (R2).

7. Enquiry form: visitors browse freely; the form appears only when they ask for a price sheet, sample or quote.

8. AI assistant (Koko): low-cost AI provider during development; final choice tested before go-live.

9. Domain (web address): to be decided at deployment.



---------------------------------------------------------------------------------------------------

## 5. What we need from KJS

1. Logo, brand colours, factory and product photos, first offers.  (by 2 Nov)

2. Product list: categories, pack sizes, minimum order, certifications, best sellers.  (by 2 Nov)

3. Employee list and holiday list 2026–27.  (by 9 Nov)

4. Server access and an IT contact.  (early Nov)

5. WhatsApp Business verification started (for alerts).  (as soon as possible, takes 1–2 weeks)

6. FAQs and policies for Koko.  (by 13 Nov)

7. Order steps, who receives deadline alerts, and 2 or 3 sample requirement files.  (by 20 Nov)

8. Confirm the partner programme offer (commission, referral link) shown on the Partners page.  (before go-live)

9. Email account for sending notifications (SMTP details).  (before testing)

10. Buyer lists to work through (Excel), one product category per row.  (before testing)



---------------------------------------------------------------------------------------------------

## 6. Updates from Vineet

Add changes here, newest at the bottom, like this:

   [update: what it refers to, date] the change

1. [update: Roles, 23 Oct] Removed the Manager role. Admin and Employee only.



---------------------------------------------------------------------------------------------------

## 7. Progress notes

1. 23 Oct

   First working version on a laptop. The public website uses the real KJS logo, photos, videos and text from
   kjsindia.com. Visitors can send enquiries or chat with the AI assistant (it answers in their language and never
   quotes prices). Staff can sign up; the admin approves them and chooses what each person may do. Every change
   is recorded in a history log that cannot be edited.


2. 24 Oct

   Every feature planned for launch now works on a laptop and passed a full test run in a real browser.

   i.    Website: price sheet, spec sheet, sample and quote requests (asked once, then remembered), offers strip,
         WhatsApp button, partner programme page, private-label builder.
   ii.   Employees: check-in and out with weekly hours and missed-punch requests, "receiving tasks" switch,
         tasks, leads with response timers, automatic work batches, order boards, notifications, profile.
   iii.  Admin: all leads, approvals in one place, team attendance, order boards with deadline alerts,
         automatic assignment, products with photos, website text and offers editor, AI assistant facts and
         chat history, charts, settings.
   iv.   Next: production setup, real data from KJS.


3. 25 Oct

   The setup for the KJS server is ready: it installs the whole system with one command, makes a backup every
   night, and can be updated or rolled back safely. We tested a full "backup, lose data, restore" exercise and
   everything came back. Nothing on the server is open to the internet; visitors arrive through Cloudflare.
   Next: we need the server, an IT contact and the web address to put it live.


4. 28 Oct

   The new home page is ready: a catalogue of 58 KJS products with pictures, search, a category menu and an
   enquiry list buyers can send in one go. Our development database moved from the USA to Singapore, so pages
   that read data answer several times faster from India.


5. 30 Oct

   The home page now suggests products to returning visitors, and product cards appear with a short animation
   as visitors scroll. Staff now see a loading spinner when they log in; if the server is slow or down, they
   get a clear message with "Try again" and "Log out" instead of an endless wait. Next: a sidebar that slides
   in and out, partner page updates, best-seller offers, and country and phone-code pickers with flags.
