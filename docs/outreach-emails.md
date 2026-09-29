# Outreach Emails — requesting official access to MTC racing data

Copy, fill in the bracketed parts, and send. Worth trying in parallel: **MTC
Jockey Club** (publisher of the form guide), the **Gambling Regulatory
Authority** (`gra.govmu.org`, regulator of the sport's betting — they know who
holds the data rights), and **Racing and Sports** (Australia): the MTC site is
powered by their `MTCRaceSystem` (race cards, silks, photo-finish, the per-race
result PDFs all live under `racingandsports.com.au/MTCRaceSystem/`), so they may
license the Mauritius feed directly.

---

## 1. To MTC Jockey Club (English)

> **Subject:** Request for permission / official data access — MTC form guide, results and ratings
>
> Dear Sir or Madam,
>
> I am a Mauritius-based software developer working on a **personal,
> non-commercial** horse-racing analytics project (no betting, no resale, no
> redistribution of your data).
>
> I would like to use MTC data: race cards, runners, jockeys/trainers, results,
> starting prices, official ratings, and the per-race result PDF you publish.
>
> When I tested programmatic access, `mtcjockeyclub.com` (including its
> `robots.txt`) returned HTTP 403 behind Cloudflare, so **I have not attempted to
> bypass your bot protection**, and I am not scraping the site. Instead I am
> asking:
>
> 1. Do you offer an official data feed, API, or scheduled export (CSV/JSON/XLSX/FTP)?
> 2. If not, may I have **written permission** to retrieve the publicly published
>    form-guide and result pages at a low, polite rate — clearly identified
>    User-Agent, a few seconds between requests, one pass per meeting day?
> 3. If data licensing is handled elsewhere, could you point me to the right
>    contact? I believe your race system is operated with Racing and Sports.
>
> I am happy to sign any terms you require and to pay a reasonable fee for
> licensed access. I will not redistribute the data and will not use it for
> wagering.
>
> Thank you for your time and for the racing programme.
>
> Kind regards,
> [Your name] · [phone] · [email]

---

## 2. To MTC Jockey Club (Français)

> **Objet :** Demande d'autorisation / d'accès officiel aux données — form guide, résultats et ratings de la MTC
>
> Madame, Monsieur,
>
> Je suis développeur informatique à Maurice et je travaille sur un projet
> **personnel et non commercial** d'analyse des courses hippiques (aucun pari,
> aucune revente, aucune redistribution de vos données).
>
> Je souhaiterais utiliser les données de la MTC : programmes/cartes de course,
> partants, jockeys/entraîneurs, résultats, cotes de départ (SP), ratings
> officiels, ainsi que le PDF de résultat publié par course.
>
> Lors de mes tests d'accès automatisé, `mtcjockeyclub.com` (y compris son
> `robots.txt`) a répondu HTTP 403 via Cloudflare. **Je n'ai donc pas tenté de
> contourner votre protection anti-robots** et je ne pratique aucun scraping du
> site. C'est pourquoi je vous adresse les questions suivantes :
>
> 1. Proposez-vous un flux de données officiel, une API ou un export programmé
>    (CSV/JSON/XLSX/FTP) ?
> 2. Sinon, puis-je obtenir une **autorisation écrite** pour consulter les pages
>    publiques du form guide et des résultats à un rythme réduit et respectueux
>    (User-Agent clairement identifié, quelques secondes entre les requêtes, une
>    passe par journée de courses) ?
> 3. Si la gestion des données relève d'un autre service, pourriez-vous
>    m'indiquer le bon interlocuteur ? Il me semble que votre système de courses
>    fonctionne avec Racing and Sports.
>
> Je suis prêt à signer les conditions que vous jugerez nécessaires et à payer un
> tarif raisonnable pour un accès sous licence. Je ne redistribuerai pas les
> données et ne les utiliserai pas pour des paris.
>
> Je vous remercie par avance de votre retour.
>
> Cordialement,
> [Votre nom] · [téléphone] · [email]

---

## 3. To the Gambling Regulatory Authority (English — short)

> **Subject:** Who licenses Mauritius race data? (personal analytics project)
>
> Dear Sir or Madam,
>
> I am building a personal, non-commercial horse-racing analytics project and I
> would like to use official MTC data (race cards, results, starting prices,
> ratings). MTC's website blocks automated clients, so I am looking for the
> proper route.
>
> Could you tell me **who holds the data rights for MTC racing data** and to whom
> licensing requests should be addressed? If a licence is required for a
> non-commercial personal project, I would be grateful for guidance on the
> process and any applicable fees.
>
> Thank you for your time.
>
> Kind regards,
> [Your name] · [phone] · [email]

---

## 4. To Racing and Sports (data licensing — English)

> **Subject:** Data licensing enquiry — Mauritius Turf Club feed (MTC / Champ de Mars)
>
> Hello,
>
> Your MTCRaceSystem powers the Mauritius Turf Club website (form guide, results,
> silks, photo-finish and the per-race result PDFs). I am building a personal,
> non-commercial analytics project for Mauritius racing and would like to know:
>
> 1. Do you license the Mauritius (MTC) feed — race cards, runners, results,
>    starting prices and tote dividends — to individuals or small developers?
> 2. What is the delivery format and update frequency, and is a historical
>    archive available?
> 3. What are the licence terms and indicative cost for a single developer with
>    **no redistribution**?
> 4. If direct licensing is not offered, whom would you recommend in Mauritius?
>
> Thank you — happy to sign an NDA or any standard agreement.
>
> Kind regards,
> [Your name] · [phone] · [email]

---

## Meanwhile — you don't have to wait for replies

Real MTC data can go in today, from what you can view or download yourself:

```powershell
# save the race page in your browser (Ctrl+S, "Webpage, HTML only"),
# download the per-race result PDF, then:
.\run-pipeline.ps1 import ".\Horses data\*.pdf" ".\Horses data\*.html"
```

Verified on your own files: 6 runners with trainers, jockeys, barriers, weights,
SP, official ratings, gear, body weight + delta and **MTC horse ids**, plus
finish positions, margins, times, sectional splits and the full tote dividend
ladder (Win / Place / Swinger / Exacta / Trifecta / Quartet). The same command
works for the browser capture bookmarklet (`tools/formedge-capture.js`) and the
inbox watcher (`.\run-pipeline.ps1 watch`).

Where to find contacts: MTC's contact page (you can read it in your browser even
though my client cannot), `gra.govmu.org` → Contact, and
`racingandsports.com.au` → Contact / Data services.

