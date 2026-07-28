from __future__ import annotations

from dataclasses import dataclass
import json
import re
import unicodedata
from typing import Any, Mapping

from bot.services.product_truth import get_safe_answer_payload, list_capabilities


_PRODUCT_TRUTH_OVERVIEW_IDS = (
    'create_invoice',
    'show_existing_invoice',
    'invoice_analytics',
    'accounting_document_analytics',
    'invoice_due_date_reminders',
    'mark_existing_invoice_paid',
    'accounting_document_categories',
    'receipt_analytics',
    'edit_existing_invoice',
    'delete_existing_invoice',
    'invoice_pdf_generation',
    'add_receipt_or_incoming_invoice',
    'show_recent_accounting_documents',
    'contacts',
    'service_aliases',
    'business_profiles',
    'voice_invoice_intake',
    'customization_requests',
    'admin_customization_review',
    'admin_response_to_user',
    'admin_response_delivery_observability',
    'access_request_approval',
    'send_invoice_email',
    'google_drive_invoice_storage',
    'google_drive_invoice_archive_after_due_date',
    'sms_reminders',
    'accounting_export',
    'bank_cashflow_tax_analytics',
    'invoice_pdf_custom_template',
    'delete_user_database',
    'work_time_tracking',
    'runtime_issue_intake',
)

_RESERVED_INTENT_CAPABILITIES = {
    'send_invoice': 'send_invoice_email',
}

_STATUS_LABELS = {
    'supported': 'podporované',
    'partial': 'čiastočné',
    'planned': 'plánované',
    'unsupported': 'nepodporované',
    'unknown': 'neznáme',
}

_ACCOUNT_STATUS_LABELS = {
    'ready': 'pripravené',
    'requires_setup': 'vyžaduje nastavenie účtu',
    'requires_admin': 'vyžaduje správcu',
    'requires_external_credentials': 'vyžaduje externé prístupy',
    'unknown': 'neznáme',
}
_SLOVAK_CAPABILITY_COPY = {
    'create_invoice': {
        'title': 'Vytvorenie faktúry',
        'summary': 'Vytvorenie odosielanej faktúry je podporované cez existujúci fakturačný tok.',
        'limitation': 'Bežné použitie vyžaduje autorizovaného používateľa, profil dodávateľa, službu a kontakt.',
        'safe_next': 'Ak chcete faktúru naozaj vytvoriť, napíšte konkrétne údaje faktúry alebo použite /invoice.',
    },
    'invoice_period_summary': {
        'title': 'Ročný súhrn v analytike faktúr',
        'summary': 'Jednoduchý ročný súhrn uložených vystavených faktúr je interná read-only vetva pod analytikou faktúr.',
        'limitation': 'Nie je to samostatná verejná top-level akcia. Počítam iba už uložené odoslané faktúry vo vašom účte podľa dátumu vystavenia. Nepočítam bločky, výdavky, prijaté faktúry, banku, cashflow, DPH ani dane.',
        'safe_next': 'Napíšte napríklad: „Na akú sumu som vystavil faktúry tento rok?“ alebo širšiu otázku cez analytiku vystavených faktúr.',
    },
    'invoice_analytics': {
        'title': 'Analytika vystavených faktúr',
        'summary': 'Analytika vystavených faktúr je podporovaná čiastočne ako read-only pilot nad uloženými odoslanými faktúrami.',
        'limitation': 'Pilot pracuje iba s odoslanými faktúrami aktuálneho dodávateľa. Používa normalizovaný stav úhrady v bota, nie surový lifecycle status faktúry. Neuhradené faktúry znamenajú čakajúce aj po splatnosti; stíšená pripomienka ešte nie je úhrada. Nepočíta bločky, prijaté faktúry, bankové pohyby, dane ani všeobecné účtovné závery a nič nemení v databáze.',
        'safe_next': 'Môžete sa opýtať napríklad na faktúry za máj, porovnanie dvoch období, neuhradené/zaplatené faktúry alebo top odberateľov podľa sumy faktúr.',
    },
    'accounting_document_analytics': {
        'title': 'Analytika bločkov a prijatých faktúr',
        'summary': 'Analytika bločkov a prijatých faktúr je podporovaná čiastočne ako read-only pilot nad potvrdenými účtovnými dokladmi aktuálneho workspace.',
        'limitation': 'Pracuje iba s potvrdenými bločkami a prijatými faktúrami. Vie robiť ohraničené počty, sumy, kategórie, dodávateľov, obdobia a zoznamy. Nerobí banku, cashflow, DPH/daňový report, účtovný export ani plné účtovné závery a nič nemení v databáze.',
        'safe_next': 'Môžete sa opýtať napríklad: Koľko som minul na palivo tento mesiac?, Koľko bolo bločkov v kategórii materiál?, Ukáž sumy podľa kategórií za jún alebo Koľko som minul v BAUHAUS?',
    },
    'receipt_analytics': {
        'title': 'Analytika bločkov',
        'summary': 'Analytika bločkov je podporovaná čiastočne cez širší read-only runtime analytiky bločkov a prijatých faktúr.',
        'limitation': 'Počíta iba potvrdené bločky v aktuálnom workspace a podľa otázky aj prijaté faktúry ako výdavkové doklady. Kategórie sú metadata z príjmu dokladu, nie daňové alebo účtovné schválenie. Banka, cashflow, DPH, dane, účtovný export a plná účtovná analytika nie sú implementované.',
        'safe_next': 'Môžete sa pýtať na súčty, počty, kategórie, dodávateľov, mesiace alebo obmedzené zoznamy potvrdených bločkov.',
    },
    'accounting_document_categories': {
        'title': 'Kategórie bločkov a prijatých faktúr',
        'summary': 'Kategorizácia bločkov a prijatých faktúr je podporovaná čiastočne v existujúcom upload toku.',
        'limitation': 'Nie je to samostatná top-level akcia. Model môže iba navrhnúť kategóriu z povoleného zoznamu alebo unknown_review; Python validuje, používateľ potvrdí a až finálne uloženie zapíše metadata. Nové pracovné kategórie vznikajú iba po potvrdení.',
        'safe_next': 'Použite /add_blocek alebo /dodat_blocek, nahrajte fotku/PDF, skontrolujte navrhnutú kategóriu v náhľade a potvrďte uloženie.',
    },
    'invoice_due_date_reminders': {
        'title': 'Pripomienky faktúr po splatnosti',
        'summary': 'Pripomienky faktúr po splatnosti sú podporované čiastočne cez automatickú kontrolu v Telegrame.',
        'limitation': 'Automatická kontrola beží ako interný background scheduler s predvolenou dennou kontrolou. Emailové/SMS pripomienky a bankové párovanie nie sú zapnuté. Google Drive archivácia funguje iba v owner OAuth režime pre jedno nakonfigurované vlastnícke Google konto.',
        'safe_next': 'Keď bot nájde faktúru po splatnosti, pošle Telegram kartu. Pri každej faktúre môžete zvoliť označiť ako zaplatenú, pripomenúť neskôr alebo viac nepripomínať.',
    },
    'send_invoice_email': {
        'title': 'Odosielanie faktúr emailom',
        'summary': 'Automatické odosielanie faktúr emailom priamo z bota nie je v aktuálnej verzii implementované.',
        'limitation': 'Emailové údaje môžu existovať v kontaktoch, ale neexistuje podporovaný odosielací tok.',
        'safe_next': 'PDF môžete v Telegrame manuálne preposlať cez „Preposlať“. Ak ho chcete poslať emailom, použite „Zdieľať“ alebo „Stiahnuť“ a priložte PDF ručne vo vlastnej emailovej aplikácii; adresu príjemcu aj text emailu vypĺňate ručne.',
    },
    'google_drive_invoice_storage': {
        'title': 'Ukladanie faktúr na Google Drive',
        'summary': 'Google Drive archivácia je podporovaná čiastočne v owner OAuth režime pre jedno nakonfigurované vlastnícke Google konto.',
        'limitation': 'Nie je to per-client OAuth ani všeobecná SaaS synchronizácia. Vyžaduje OAuth client credentials, GOOGLE_TOKEN_CRYPTO_SECRET, jednorazový owner OAuth bootstrap, encrypted refresh token, root folder id v osobnom My Drive a zapnutý worker. Service-account režim nie je podporovaný pre personal My Drive bez Workspace/Shared Drive. Potvrdené bločky a prijaté faktúry sa zaraďujú asynchrónne pod samostatný priečinok vlastníckeho business profilu; lokálne uloženie neznamená úspešný upload, metadata ostávajú lokálne a staré Drive súbory sa automaticky nepresúvajú. PDF faktúr ostáva lokálne v bote.',
        'safe_next': 'Správca musí nastaviť GOOGLE_DRIVE_ENABLED=1, owner OAuth credentials, GOOGLE_TOKEN_CRYPTO_SECRET, uložiť encrypted refresh token cez bootstrap a nastaviť GOOGLE_DRIVE_ROOT_FOLDER_ID. Potom worker nahráva potvrdené doklady a vybrané faktúry do Drive archívu.',
    },
    'google_drive_invoice_archive_after_due_date': {
        'title': 'Archivácia faktúry na Google Drive po splatnosti',
        'summary': 'Po potvrdenom rozhodnutí pri faktúre po splatnosti, napríklad po označení ako uhradená, vie nakonfigurovaný owner OAuth Drive režim zaradiť PDF do archívu.',
        'limitation': 'Ak Drive nie je nakonfigurovaný, ostáva iba lokálny stub a nič sa nenahráva. Upload prebieha cez worker; úspech sa nesmie tvrdiť pred stavom uploaded. Lokálny PDF faktúry sa v tomto MVP nemaže.',
        'safe_next': 'Najprv potvrďte stav faktúry. Pri zapnutom Drive režime sa PDF zaradí do fronty; pri vypnutom režime zostáva lokálne bez tvrdenia o uploade.',
    },
    'sms_reminders': {
        'title': 'SMS pripomienky',
        'summary': 'SMS pripomienky nie sú v aktuálnej verzii implementované.',
        'limitation': 'Nie je implementovaný SMS poskytovateľ, súhlasy, telefónne čísla ani plánovanie odosielania.',
        'safe_next': 'SMS by vyžadovali poskytovateľa, pravidlá súhlasu, cenu a samostatné testy.',
    },
    'accounting_export': {
        'title': 'Export do účtovníctva',
        'summary': 'Export do účtovného softvéru nie je v aktuálnej verzii implementovaný.',
        'limitation': 'Aktuálne účtovné dokumenty pokrývajú iba potvrdený príjem dokladov a nedávny prehľad tam, kde je podporený.',
        'safe_next': 'Export by potreboval cieľový softvér, formát alebo API, prístupy a samostatné schválenie.',
    },
    'bank_cashflow_tax_analytics': {
        'title': 'Banková, cashflow, DPH a daňová analytika',
        'summary': 'Bankové pohyby, cashflow, DPH/daňové výpočty a plná účtovná analytika nie sú v aktuálnom runtime implementované.',
        'limitation': 'Pilot analytiky pracuje iba s uloženými odoslanými faktúrami. Nemá bankové výpisy, párovanie platieb, cashflow model, DPH report ani daňové poradenstvo.',
        'safe_next': 'Takáto analytika by potrebovala samostatné zdroje dát, pravidlá validácie, Product Truth, testy a schválený rozsah.',
    },
    'invoice_pdf_custom_template': {
        'title': 'Vlastná PDF šablóna faktúry',
        'summary': 'Vlastná alebo stará PDF šablóna nie je v aktuálnej verzii dostupná.',
        'limitation': 'Faktúry sa generujú podľa zabudovaného rozloženia FakturaBotu.',
        'safe_next': 'Na vlastnú šablónu by bola potrebná samostatná úprava a kontrola PDF rozloženia.',
    },
    'customization_requests': {
        'title': 'Požiadavky na úpravu',
        'summary': 'Požiadavku alebo otázku na ľudskú kontrolu viem pripraviť na kontrolu správcom.',
        'limitation': 'Uloženie neznamená automatickú implementáciu, zmenu Product Truth, backlog ani úlohu pre code agenta.',
        'safe_next': 'Ak chcete, môžem z toho pripraviť požiadavku na kontrolu správcom. Uloží sa iba vtedy, keď ju potvrdíte.',
    },
    'admin_customization_review': {
        'title': 'Posúdenie požiadavky správcom',
        'summary': 'Správca vie požiadavku vidieť v zozname/detaili a označiť ju ako prijatú alebo zamietnutú na úrovni stavu.',
        'limitation': 'Prijatá požiadavka nie je sľub implementácie. Zamietnutá požiadavka neznamená automatickú notifikáciu, ak správca neposlal samostatnú odpoveď.',
        'safe_next': 'Stav prijatá/zamietnutá berte ako výsledok posúdenia, nie ako zmenu schopností produktu.',
    },
    'admin_response_to_user': {
        'title': 'Odpoveď správcu používateľovi',
        'summary': 'Správca vie cez potvrdený admin tok poslať používateľovi jednu odpoveď k pôvodnej požiadavke.',
        'limitation': 'MVP podporuje iba odpoveď typu answer, bez vlákna, automatického retry, SLA alebo sľubu doručenia.',
        'safe_next': 'Ak správca odpoveď odošle, príde vám ako správa bota. Samotná odpoveď nemení Product Truth ani nepodporuje novú funkciu.',
    },
    'admin_response_delivery_observability': {
        'title': 'Stav doručenia odpovede správcu',
        'summary': 'Správca v detaile požiadavky vidí stav doručenia odpovede, pokusy, čas a bezpečne orezaný náhľad.',
        'limitation': 'Tieto interné doručovacie údaje sú admin-facing. Používateľovi sa nezobrazuje kompletná doručovacia diagnostika.',
        'safe_next': 'Ak odpoveď nedorazila, treba to riešiť ručne so správcom; bot v MVP neskúša automatické opakovanie.',
    },
    'access_request_approval': {
        'title': 'Žiadosť o prístup a schválenie',
        'summary': 'Neznámy používateľ môže požiadať o prístup a správca ho musí schváliť pred biznis tokmi.',
        'limitation': 'Čakajúca žiadosť ešte nie je aktívny účet, profil dodávateľa ani oprávnenie vytvárať dáta.',
        'safe_next': 'Požiadajte o prístup a počkajte na schválenie správcom.',
    },
    'runtime_issue_intake': {
        'title': 'Nahlásenie prevádzkového problému',
        'summary': 'Správca môže uložiť jeden konkrétny pozorovaný problém bota cez /issue, ohraničený text alebo hlas.',
        'limitation': 'Uloženie nepotvrdzuje chybu, nespúšťa diagnostiku ani opravu a nesľubuje termín. Aktívna biznis akcia zostane nezmenená.',
        'safe_next': 'Ak ste správca a chcete problém uložiť, pošlite /issue a úplný opis v tej istej správe.',
    },
    'business_profiles': {
        'title': 'Viac firemných profilov',
        'summary': 'Jeden autorizovaný používateľ môže čiastočne používať viac izolovaných business profilov a explicitne medzi nimi prepínať.',
        'limitation': 'Prepnutie je iba explicitné cez /profily alebo switch intent. Cross-workspace analytika, jednorazové override, vymazanie jedného profilu a multi-member administrácia nie sú v MVP. Existujúca serverová DB vyžaduje schválenú migráciu pred deployom.',
        'safe_next': 'V idle stave použite /profily a vyberte iba profil, ku ktorému máte membership.',
    },
    'contacts': {
        'title': 'Kontakty',
        'summary': 'Kontakt môžete pridať manuálne alebo z dokumentu; pri zapnutom pilote môžete slovenskú firmu vyhľadať podľa názvu alebo IČO. Presná zhoda potlačí slabý šum, podobné návrhy vždy vyberáte ručne a oficiálne dostupné údaje sa zobrazia v náhľade.',
        'limitation': 'Vyhľadávanie RPO je predvolene vypnuté a môže byť obmedzené na pilotný profil. RPO poskytuje identitu a adresu. Voliteľné doplnenie DIČ/IČ DPH z Finančnej správy používa overenú oficiálnu API mapu, ale stále vyžaduje samostatné zapnutie a API kľúč; pri vypnutí, chybe, neplatnom, nejednoznačnom alebo chýbajúcom DIČ sa hodnota dopĺňa textom. IČ DPH sa nikdy nevytvára z DIČ, komerčné weby sa nescrapujú a kontakty sa na pozadí nesynchronizujú.',
        'safe_next': 'Použite /contact, /contact_add alebo /add_kontakt, skontrolujte náhľad a kontakt uložte až explicitným potvrdením.',
    },
    'service_aliases': {
        'title': 'Služby a položky',
        'summary': 'Službu alebo položku pre faktúry môžete uložiť ako dodávateľský alias.',
        'limitation': 'Presný názov aliasu a zobrazovaný text sú textové kroky; hlas ich nemá vypĺňať ako finálne presné hodnoty.',
        'safe_next': 'Použite /sluzbu alebo napíšte, že chcete pridať službu/položku, a pokračujte cez potvrdený tok.',
    },
    'show_recent_accounting_documents': {
        'title': 'Posledné bločky a účtovné doklady',
        'summary': 'Nedávne potvrdené bločky a prijaté faktúry sa dajú zobraziť v read-only prehľade.',
        'limitation': 'Nie je to plný dokumentový vyhľadávač, editor, mazanie ani Google Drive synchronizácia.',
        'safe_next': 'Použite /blocek alebo /blocky na zobrazenie posledných uložených dokladov.',
    },
    'edit_existing_invoice': {
        'title': 'Úprava existujúcej faktúry',
        'summary': 'Existujúcu odoslanú faktúru možno upraviť cez ohraničený tok po vyhľadaní konkrétnej faktúry.',
        'limitation': 'Číslo faktúry a presné upravované hodnoty sú citlivé na presnosť a patria do textu.',
        'safe_next': 'Napíšte, ktorú faktúru chcete upraviť, a pokračujte cez existujúci edit flow.',
    },
    'mark_existing_invoice_paid': {
        'title': 'Označenie faktúry ako uhradenej',
        'summary': 'Jednu uloženú vystavenú faktúru možno po vyhľadaní označiť ako uhradenú.',
        'limitation': 'Je to len stav uložený v bote. Nie je to bankové potvrdenie, párovanie platby ani reálny Google Drive upload.',
        'safe_next': 'Napíšte alebo povedzte napríklad: „označ faktúru 04 ako uhradenú“ a potvrďte tlačidlom.',
    },
    'delete_existing_invoice': {
        'title': 'Vymazanie jednej faktúry',
        'summary': 'Jednu uloženú faktúru možno vymazať len po vyhľadaní a explicitnom potvrdení.',
        'limitation': 'Vymazanie je deštruktívne; hlas môže tok spustiť, ale potvrdenie zostáva bezpečnostne ohraničené.',
        'safe_next': 'Napíšte, ktorú faktúru chcete vymazať, a potvrďte až po kontrole náhľadu.',
    },
    'work_time_tracking': {
        'title': 'Evidencia pracovneho casu / Dochadzka',
        'summary': 'Evidencia pracovneho casu je podporovana ciastocne: bot vie otvorit a uzavriet pracovny den, doplnit potvrdeny casovy rozsah, nastavit odpocty obednej prestavky, vytvorit mesacny Excel vykaz a po potvrdeni vymazat ulozene zaznamy za vybrany mesiac.',
        'limitation': 'Nie je to mzdova dochadzka, vypocet mzdy, pravna HR evidencia, multi-zamestnanecka dochadzka ani export do uctovneho alebo mzdoveho softveru. Bot automaticky nevie, kedy ste pracovali; cas treba zadat alebo otvorit/uzavriet. Obedna prestavka je fixny pouzivatelsky odpocet pre vykazy, nie pravny payroll vypocet. Vymazanie mesiaca maze DB zaznamy dochadzky, nie on-demand Excel subory ako kanonicke data.',
        'safe_next': 'Pouzite napriklad: zacinam pracovny den, zatvor den o 17:00, pracoval som dnes od 5:30 do 17:00, vytvor vykaz hodin za jun 2026, nastav obednu prestavku na 30 minut alebo vymaz dochadzku za jul 2026. Hlasom mozete zacat a ovladat tok; presne casy, zmena obeda aj mazanie mesiaca idu az po nahlade a potvrdeni.',
    },
    'code_agent_handoff': {
        'title': 'Odovzdanie úlohy kódovaciemu agentovi',
        'summary': 'Odovzdanie úlohy kódovaciemu agentovi z Telegram bota nie je implementované.',
        'limitation': 'Implementačné úlohy stále vyžadujú ľudskú kontrolu a nie sú vytvárané Telegram botom.',
        'safe_next': 'Bot nesmie sľúbiť patch, merge, deploy ani odovzdanie agentovi.',
    },
    'add_receipt_or_incoming_invoice': {
        'title': 'Pridanie bločku alebo prijatej faktúry',
        'summary': 'Príjem bločku alebo prijatej faktúry je podporovaný čiastočne cez existujúci upload tok.',
        'limitation': 'Vyžaduje sa fotka alebo PDF; úprava a širšie typy dokumentov nie sú súčasťou tohto toku.',
        'safe_next': 'Použite /add_blocek alebo požiadajte o pridanie bločku a potom nahrajte fotku alebo PDF.',
    },
    'voice_invoice_intake': {
        'title': 'Hlasové zadanie faktúry',
        'summary': 'Hlas vie spustiť fakturačný tok a niektoré voľby, ale presné hodnoty zostávajú textové.',
        'limitation': 'IBAN, IČO, DIČ, email, čísla faktúr, sumy a presné popisy patria do textu alebo súboru.',
        'safe_next': 'Hlas používajte na zámer a bežné ovládanie; presné hodnoty zadajte textom.',
    },
    'delete_user_database': {
        'title': 'Vymazanie používateľskej databázy',
        'summary': 'Vymazanie používateľských dát je podporované len cez bezpečnostný tok s presným potvrdením.',
        'limitation': 'Hlas môže spustiť varovanie, ale finálne vymazanie vyžaduje presnú napísanú frázu.',
        'safe_next': 'Ak to chcete naozaj urobiť, použite bezpečnostný tok a postupujte podľa presnej výzvy.',
    },
}
_SLOVAK_OVERVIEW_TITLES = {
    'create_invoice': 'vytvorenie faktúry',
    'show_existing_invoice': 'zobrazenie existujúcej faktúry',
    'invoice_period_summary': 'ročný súhrn v analytike faktúr',
    'invoice_analytics': 'analytika vystavených faktúr',
    'accounting_document_analytics': 'analytika bločkov a prijatých faktúr',
    'invoice_due_date_reminders': 'pripomienky faktúr po splatnosti',
    'mark_existing_invoice_paid': 'označenie faktúry ako uhradenej',
    'accounting_document_categories': 'kategórie bločkov a prijatých faktúr',
    'receipt_analytics': 'analytika bločkov',
    'edit_existing_invoice': 'úprava existujúcej faktúry',
    'delete_existing_invoice': 'vymazanie existujúcej faktúry',
    'invoice_pdf_generation': 'generovanie PDF faktúry',
    'add_receipt_or_incoming_invoice': 'pridanie bločku alebo prijatej faktúry',
    'show_recent_accounting_documents': 'prehľad nedávnych účtovných dokladov',
    'contacts': 'kontakty',
    'business_profiles': 'viac firemných profilov',
    'service_aliases': 'služby a položky',
    'voice_invoice_intake': 'hlasové zadanie faktúry',
    'customization_requests': 'požiadavky na úpravu a ľudskú kontrolu',
    'admin_customization_review': 'posúdenie požiadavky správcom',
    'admin_response_to_user': 'odpoveď správcu používateľovi',
    'admin_response_delivery_observability': 'stav doručenia odpovede správcu',
    'access_request_approval': 'žiadosť o prístup a schválenie',
    'send_invoice_email': 'odosielanie faktúr emailom',
    'google_drive_invoice_storage': 'ukladanie faktúr na Google Drive',
    'google_drive_invoice_archive_after_due_date': 'archivácia faktúry na Google Drive po splatnosti',
    'sms_reminders': 'SMS pripomienky',
    'accounting_export': 'export do účtovníctva',
    'bank_cashflow_tax_analytics': 'banková, cashflow, DPH a daňová analytika',
    'invoice_pdf_custom_template': 'vlastná PDF šablóna faktúry',
    'delete_user_database': 'vymazanie používateľskej databázy',
}

_HELP_CUES = {
    'ako',
    'co',
    'cim',
    'preco',
    'vie',
    'vies',
    'viete',
    'mozes',
    'mozete',
    'da',
    'dokazes',
    'podporujes',
    'podporujete',
    'funguje',
    'can',
    'could',
    'how',
    'what',
    'why',
    'support',
    'supports',
}
_OVERVIEW_PHRASES = (
    'co vies',
    'co dokazes',
    's cim mi vies pomoct',
    's cim viete pomoct',
    'ake funkcie',
    'what can you do',
    'what do you support',
)
_DIRECT_ACTION_GUARD_WORDS = {
    'vytvor',
    'sprav',
    'urob',
    'zrob',
    'pridaj',
    'dodaj',
    'nahraj',
    'posli',
    'vymaz',
    'zmaz',
    'uprav',
    'zobraz',
    'ukaz',
}

TRIAGE_KNOWN_PRODUCT_CAPABILITY = 'known_product_capability'
TRIAGE_NEW_BUSINESS_FEATURE_REQUEST = 'new_business_feature_request'
TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE = 'customization_request_candidate'
TRIAGE_ADMIN_REVIEW_CANDIDATE = 'admin_review_candidate'
TRIAGE_OUT_OF_DOMAIN = 'out_of_domain'
TRIAGE_SPAM_OR_ABUSE = 'spam_or_abuse'
TRIAGE_SMALLTALK = 'smalltalk'
TRIAGE_UNCLEAR_NEEDS_CLARIFICATION = 'unclear_needs_clarification'
TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE = 'possible_product_truth_candidate'
TRIAGE_UNKNOWN = 'unknown'

ALLOWED_INFO_HELP_TRIAGE_CLASSES = (
    TRIAGE_KNOWN_PRODUCT_CAPABILITY,
    TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
    TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE,
    TRIAGE_ADMIN_REVIEW_CANDIDATE,
    TRIAGE_OUT_OF_DOMAIN,
    TRIAGE_SPAM_OR_ABUSE,
    TRIAGE_SMALLTALK,
    TRIAGE_UNCLEAR_NEEDS_CLARIFICATION,
    TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE,
    TRIAGE_UNKNOWN,
)

ALLOWED_INFO_HELP_TOPIC_IDS = (
    'product_capability',
    'new_business_feature',
    'customization_request',
    'admin_review',
    'out_of_domain',
    'spam_or_abuse',
    'smalltalk',
    'clarification',
    'possible_product_truth_candidate',
    TRIAGE_UNKNOWN,
)

_TRIAGE_TOPIC_BY_CLASS = {
    TRIAGE_KNOWN_PRODUCT_CAPABILITY: 'product_capability',
    TRIAGE_NEW_BUSINESS_FEATURE_REQUEST: 'new_business_feature',
    TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE: 'customization_request',
    TRIAGE_ADMIN_REVIEW_CANDIDATE: 'admin_review',
    TRIAGE_OUT_OF_DOMAIN: 'out_of_domain',
    TRIAGE_SPAM_OR_ABUSE: 'spam_or_abuse',
    TRIAGE_SMALLTALK: 'smalltalk',
    TRIAGE_UNCLEAR_NEEDS_CLARIFICATION: 'clarification',
    TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE: 'possible_product_truth_candidate',
    TRIAGE_UNKNOWN: TRIAGE_UNKNOWN,
}


@dataclass(frozen=True)
class InfoHelpTriageResult:
    capability_id: str = 'unknown'
    topic_id: str = 'unknown'
    triage_class: str = TRIAGE_UNKNOWN
    confidence: float = 0.0
    needs_clarification: bool = False
    business_need: str = ''
    detected_domain: str = 'other'
    expected_outcome: str = ''
    clarification_questions: tuple[str, ...] = ()
    proposed_title: str = ''
    proposed_description: str = ''
    risk_level: str = 'medium'


ALLOWED_ADMIN_REVIEW_DRAFT_DOMAINS = (
    'invoice_pdf_layout',
    'invoice_delivery',
    'invoice_storage',
    'invoice_fields',
    'reminders',
    'work_hours',
    'reports',
    'accounting_documents',
    'accounting_export',
    'contacts',
    'supplier_profile',
    'google_drive',
    'email',
    'sms',
    'access_control',
    'workspace_setup',
    'other',
)

ALLOWED_ADMIN_REVIEW_RISK_LEVELS = ('low', 'medium', 'high', 'critical')

def parse_info_help_triage_model_output(
    raw_model_output: str,
    *,
    allowed_capability_ids: tuple[str, ...] | list[str] | None = None,
    allowed_topic_ids: tuple[str, ...] | list[str] | None = None,
) -> InfoHelpTriageResult:
    """Validate bounded model classification output without accepting answer text."""
    allowed_capabilities = set(allowed_capability_ids or _known_capability_ids())
    allowed_topics = set(allowed_topic_ids or ALLOWED_INFO_HELP_TOPIC_IDS)
    try:
        parsed = json.loads(raw_model_output or '{}')
    except (TypeError, json.JSONDecodeError):
        return InfoHelpTriageResult()
    if not isinstance(parsed, dict):
        return InfoHelpTriageResult()

    capability_id = str(parsed.get('capability_id') or 'unknown').strip()
    if capability_id not in allowed_capabilities:
        capability_id = 'unknown'

    triage_class = str(parsed.get('triage_class') or TRIAGE_UNKNOWN).strip()
    invalid_triage_class = triage_class not in ALLOWED_INFO_HELP_TRIAGE_CLASSES
    if invalid_triage_class:
        triage_class = TRIAGE_UNKNOWN
    if triage_class == TRIAGE_KNOWN_PRODUCT_CAPABILITY and capability_id == 'unknown':
        triage_class = TRIAGE_UNKNOWN
    if capability_id != 'unknown' and triage_class != TRIAGE_KNOWN_PRODUCT_CAPABILITY:
        return InfoHelpTriageResult()

    topic_id = str(parsed.get('topic_id') or _TRIAGE_TOPIC_BY_CLASS.get(triage_class, TRIAGE_UNKNOWN)).strip()
    if invalid_triage_class:
        topic_id = TRIAGE_UNKNOWN
    if topic_id not in allowed_topics:
        topic_id = _TRIAGE_TOPIC_BY_CLASS.get(triage_class, TRIAGE_UNKNOWN)
    if topic_id not in allowed_topics:
        topic_id = TRIAGE_UNKNOWN

    confidence = _bounded_confidence(parsed.get('confidence'))
    needs_clarification = bool(parsed.get('needs_clarification')) or triage_class == TRIAGE_UNCLEAR_NEEDS_CLARIFICATION
    draft = parsed.get('admin_review_draft')
    if not isinstance(draft, dict):
        draft = {}
    draft_allowed = triage_class in {
        TRIAGE_NEW_BUSINESS_FEATURE_REQUEST,
        TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE,
        TRIAGE_ADMIN_REVIEW_CANDIDATE,
        TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE,
    }
    detected_domain = _bounded_choice(
        draft.get('detected_domain'),
        allowed=ALLOWED_ADMIN_REVIEW_DRAFT_DOMAINS,
        default='other',
    )
    risk_level = _bounded_choice(
        draft.get('risk_level'),
        allowed=ALLOWED_ADMIN_REVIEW_RISK_LEVELS,
        default='medium',
    )
    questions = _bounded_text_list(draft.get('clarification_questions'), max_items=4, max_length=160)
    return InfoHelpTriageResult(
        capability_id=capability_id,
        topic_id=topic_id,
        triage_class=triage_class,
        confidence=confidence,
        needs_clarification=needs_clarification,
        business_need=_bounded_text(draft.get('business_need'), max_length=500) if draft_allowed else '',
        detected_domain=detected_domain if draft_allowed else 'other',
        expected_outcome=_bounded_text(draft.get('expected_outcome'), max_length=500) if draft_allowed else '',
        clarification_questions=questions if draft_allowed else (),
        proposed_title=_bounded_text(draft.get('proposed_title'), max_length=100) if draft_allowed else '',
        proposed_description=_bounded_text(draft.get('proposed_description'), max_length=800) if draft_allowed else '',
        risk_level=risk_level if draft_allowed else 'medium',
    )


def build_product_truth_guidance(
    *,
    user_input_text: str | None,
    resolved_top_level_intent: str | None = None,
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    """Return Level 2 Product Truth guidance for a conservative InfoHelp topic."""
    capability_id = classify_info_help_capability(
        user_input_text=user_input_text,
        resolved_top_level_intent=resolved_top_level_intent,
    )
    if capability_id is None:
        return None
    if capability_id == 'overview':
        return _build_capability_overview()
    payload = get_safe_answer_payload(capability_id, account_context=account_context)
    return _render_product_truth_payload(payload)


def classify_info_help_triage(*, user_input_text: str | None) -> InfoHelpTriageResult:
    """Classify unresolved InfoHelp input into Python-owned safe triage classes."""
    capability_id = classify_info_help_capability(user_input_text=user_input_text)
    if capability_id is not None and capability_id != 'overview':
        return InfoHelpTriageResult(
            capability_id=capability_id,
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.9,
        )
    if capability_id == 'overview':
        return InfoHelpTriageResult(
            capability_id='unknown',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.9,
        )

    raw_text = user_input_text or ''
    normalized = _normalize_text(raw_text)
    if not normalized:
        if raw_text.strip():
            return _triage_result(TRIAGE_SPAM_OR_ABUSE, confidence=0.75)
        return InfoHelpTriageResult(needs_clarification=True)
    tokens = set(normalized.split())

    if _is_noise_or_abuse(normalized, tokens):
        return _triage_result(TRIAGE_SPAM_OR_ABUSE, confidence=0.75)
    if _is_smalltalk(normalized, tokens):
        return _triage_result(TRIAGE_SMALLTALK, confidence=0.85)
    if _is_unclear_request(normalized, tokens):
        return _triage_result(TRIAGE_UNCLEAR_NEEDS_CLARIFICATION, confidence=0.85, needs_clarification=True)
    if _is_out_of_domain(normalized, tokens):
        return _triage_result(TRIAGE_OUT_OF_DOMAIN, confidence=0.85)
    if _is_admin_review_request(normalized, tokens):
        return _triage_result(TRIAGE_ADMIN_REVIEW_CANDIDATE, confidence=0.8)
    if _is_invoice_period_summary_request(normalized, tokens):
        return InfoHelpTriageResult(
            capability_id='invoice_analytics',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.85,
        )
    if _is_invoice_analytics_request(normalized, tokens):
        return InfoHelpTriageResult(
            capability_id='invoice_analytics',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.8,
        )
    if _mentions_bank_cashflow_tax_analytics(normalized, tokens):
        return InfoHelpTriageResult(
            capability_id='bank_cashflow_tax_analytics',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.82,
        )
    if _mentions_accounting_document_analytics_capability(normalized, tokens):
        return InfoHelpTriageResult(
            capability_id='accounting_document_analytics',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.82,
        )
    if _mentions_accounting_document_categories(normalized, tokens):
        return InfoHelpTriageResult(
            capability_id='accounting_document_categories',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.82,
        )
    if _mentions_receipt_analytics_capability(normalized, tokens):
        return InfoHelpTriageResult(
            capability_id='receipt_analytics',
            topic_id='product_capability',
            triage_class=TRIAGE_KNOWN_PRODUCT_CAPABILITY,
            confidence=0.82,
        )
    if _is_new_business_feature_request(normalized, tokens):
        return _triage_result(TRIAGE_NEW_BUSINESS_FEATURE_REQUEST, confidence=0.8)
    if _is_customization_candidate(normalized, tokens):
        return _triage_result(TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE, confidence=0.75)
    if _is_possible_product_truth_candidate(normalized, tokens):
        return _triage_result(TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE, confidence=0.6)
    return InfoHelpTriageResult()


def build_info_help_triage_guidance(
    *,
    user_input_text: str | None,
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    """Render a safe non-persistent answer for bounded InfoHelp/Triage v1."""
    result = classify_info_help_triage(user_input_text=user_input_text)
    return render_info_help_triage_result(result, account_context=account_context)


def render_info_help_triage_result(
    result: InfoHelpTriageResult,
    *,
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    return _render_info_help_triage_result(result, account_context=account_context)


async def resolve_info_help_triage_result_with_llm(
    *,
    user_input_text: str | None,
    api_key: str | None,
    model: str,
    input_channel: str = 'text',
) -> InfoHelpTriageResult:
    """Classify unresolved input deterministically first, then by bounded LLM fallback."""
    deterministic_result = classify_info_help_triage(user_input_text=user_input_text)
    deterministic_answer = _render_info_help_triage_result(deterministic_result)
    if deterministic_answer is not None:
        return deterministic_result

    from bot.services.info_help_resolver import resolve_info_help_triage_with_llm

    return await resolve_info_help_triage_with_llm(
        user_input_text=user_input_text or '',
        api_key=api_key,
        model=model,
        input_channel=input_channel,
    )


async def build_info_help_triage_guidance_with_llm(
    *,
    user_input_text: str | None,
    api_key: str | None,
    model: str,
    input_channel: str = 'text',
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    """Render deterministic triage first, then optional bounded LLM triage fallback."""
    result = await resolve_info_help_triage_result_with_llm(
        user_input_text=user_input_text or '',
        api_key=api_key,
        model=model,
        input_channel=input_channel,
    )
    return render_info_help_triage_result(result, account_context=account_context)


def _render_info_help_triage_result(
    result: InfoHelpTriageResult,
    *,
    account_context: Mapping[str, Any] | None = None,
) -> str | None:
    if result.triage_class == TRIAGE_KNOWN_PRODUCT_CAPABILITY:
        if result.capability_id != 'unknown':
            payload = get_safe_answer_payload(result.capability_id, account_context=account_context)
            return _render_product_truth_payload(payload)
        return _build_capability_overview()
    if result.triage_class == TRIAGE_NEW_BUSINESS_FEATURE_REQUEST:
        if result.business_need == 'invoice_period_summary':
            payload = get_safe_answer_payload('invoice_analytics', account_context=account_context)
            return _render_product_truth_payload(payload)
        return (
            'Toto vyzer\u00e1 ako po\u017eiadavka na nov\u00fa biznis funkciu. '
            'V aktu\u00e1lnom runtime ju neviem potvrdi\u0165 ako podporovan\u00fa.\n\n'
            'Ak chcete, m\u00f4\u017eem z toho pripravi\u0165 po\u017eiadavku na kontrolu spr\u00e1vcom. '
            'Ulo\u017e\u00ed sa iba vtedy, ke\u010f ju potvrd\u00edte.'
        )
    if result.triage_class == TRIAGE_CUSTOMIZATION_REQUEST_CANDIDATE:
        return (
            'Toto vyzer\u00e1 ako po\u017eiadavka na \u00fapravu alebo prisp\u00f4sobenie. '
            'Ak chcete, m\u00f4\u017eem z toho pripravi\u0165 po\u017eiadavku na kontrolu spr\u00e1vcom. '
            'Ulo\u017e\u00ed sa iba vtedy, ke\u010f ju potvrd\u00edte.'
        )
    if result.triage_class == TRIAGE_ADMIN_REVIEW_CANDIDATE:
        return (
            'Toto vyzer\u00e1 ako po\u017eiadavka pre spr\u00e1vcu alebo v\u00fdvoj\u00e1ra. '
            'Automatick\u00e9 odoslanie spr\u00e1vcovi nie je zapnut\u00e9.\n\n'
            'Ak chcete, m\u00f4\u017eem z toho pripravi\u0165 po\u017eiadavku na kontrolu spr\u00e1vcom. '
            'Ulo\u017e\u00ed sa iba vtedy, ke\u010f ju potvrd\u00edte.'
        )
    if result.triage_class == TRIAGE_OUT_OF_DOMAIN:
        return (
            'Toto je mimo rozsahu OfficeFlow/FakturaBotu. '
            'Viem pom\u00e1ha\u0165 s fakt\u00farami, kontaktmi, profilom dod\u00e1vate\u013ea, slu\u017ebami a \u00fa\u010dtovn\u00fdmi dokladmi.'
        )
    if result.triage_class == TRIAGE_SPAM_OR_ABUSE:
        return 'Tomuto vstupu nerozumiem. Sk\u00faste nap\u00edsa\u0165 konkr\u00e9tnu biznis \u00falohu alebo ot\u00e1zku k FakturaBotu.'
    if result.triage_class == TRIAGE_SMALLTALK:
        return (
            'Som pripraven\u00fd pom\u00f4c\u0165 s biznis \u00falohami vo FakturaBote. '
            'M\u00f4\u017eete sa op\u00fdta\u0165 na fakt\u00fary, kontakty, slu\u017eby, PDF alebo \u00fa\u010dtovn\u00e9 doklady.'
        )
    if result.triage_class == TRIAGE_UNCLEAR_NEEDS_CLARIFICATION:
        return 'Nie je jasn\u00e9, ak\u00fa biznis \u00falohu mysl\u00edte. Nap\u00ed\u0161te pros\u00edm konkr\u00e9tne, \u010do m\u00e1m spravi\u0165.'
    if result.triage_class == TRIAGE_POSSIBLE_PRODUCT_TRUTH_CANDIDATE:
        return (
            'Toto m\u00f4\u017ee by\u0165 ot\u00e1zka na schopnos\u0165 produktu, ale neviem ju bezpe\u010dne priradi\u0165 ku konkr\u00e9tnej Product Truth polo\u017eke.\n\n'
            'Ak chcete, m\u00f4\u017eem z toho pripravi\u0165 po\u017eiadavku na kontrolu spr\u00e1vcom. '
            'Ulo\u017e\u00ed sa iba vtedy, ke\u010f ju potvrd\u00edte. Product Truth sa t\u00fdm automaticky nemen\u00ed.'
        )
    return None


def classify_info_help_capability(
    *,
    user_input_text: str | None,
    resolved_top_level_intent: str | None = None,
) -> str | None:
    """Map only whitelisted informational topics to Product Truth capability ids."""
    normalized = _normalize_text(user_input_text or '')
    if not normalized:
        return None
    tokens = set(normalized.split())
    is_help_like = _is_help_like(normalized, tokens)

    if resolved_top_level_intent in _RESERVED_INTENT_CAPABILITIES:
        return _RESERVED_INTENT_CAPABILITIES[resolved_top_level_intent]

    if any(phrase in normalized for phrase in _OVERVIEW_PHRASES):
        return 'overview'

    if _mentions_email_invoice(normalized, tokens):
        return 'send_invoice_email'
    if _mentions_google_drive_invoice_archive_after_due_date(normalized, tokens):
        return 'google_drive_invoice_archive_after_due_date'
    if _mentions_google_drive(normalized, tokens):
        return 'google_drive_invoice_storage'
    if _mentions_invoice_due_date_reminders(normalized, tokens):
        return 'invoice_due_date_reminders'
    if 'sms' in tokens or 'esemes' in tokens or 'esemesky' in tokens:
        return 'sms_reminders'
    if _mentions_bank_cashflow_tax_analytics(normalized, tokens):
        return 'bank_cashflow_tax_analytics'
    if _mentions_accounting_document_analytics_capability(normalized, tokens):
        return 'accounting_document_analytics'
    if _mentions_accounting_document_categories(normalized, tokens):
        return 'accounting_document_categories'
    if _mentions_receipt_analytics_capability(normalized, tokens):
        return 'receipt_analytics'
    if _mentions_accounting_export(normalized, tokens):
        return 'accounting_export'
    if _mentions_custom_pdf_template(normalized, tokens):
        return 'invoice_pdf_custom_template'
    if _mentions_admin_response_delivery_observability(normalized, tokens):
        return 'admin_response_delivery_observability'
    if _mentions_admin_response_to_user(normalized, tokens):
        return 'admin_response_to_user'
    if _mentions_admin_review_status(normalized, tokens):
        return 'admin_customization_review'
    if _mentions_human_review_request_lifecycle(normalized, tokens):
        return 'customization_requests'
    if _mentions_customization_request(normalized, tokens):
        return 'customization_requests'
    if _mentions_access_request_approval(normalized, tokens):
        return 'access_request_approval'
    if _mentions_runtime_issue_intake(normalized, tokens):
        return 'runtime_issue_intake'
    if _mentions_code_agent_handoff(normalized, tokens):
        return 'code_agent_handoff'
    if _mentions_voice_limit(normalized, tokens):
        return 'voice_invoice_intake'
    if _mentions_business_profiles(normalized, tokens):
        return 'business_profiles'
    if _mentions_delete_database_safety(normalized, tokens):
        return 'delete_user_database'
    if _mentions_invoice_period_summary_capability(normalized, tokens) or _mentions_invoice_analytics_capability(normalized, tokens):
        return 'invoice_analytics'
    if _mentions_work_time_tracking(normalized, tokens):
        return 'work_time_tracking'
    if _mentions_mark_existing_invoice_paid(normalized, tokens):
        return 'mark_existing_invoice_paid'
    if _mentions_delete_existing_invoice_how_to(normalized, tokens):
        return 'delete_existing_invoice'
    if _mentions_edit_existing_invoice_how_to(normalized, tokens):
        return 'edit_existing_invoice'
    if _mentions_service_alias_how_to(normalized, tokens):
        return 'service_aliases'
    if _mentions_contact_how_to(normalized, tokens):
        return 'contacts'
    if _mentions_recent_accounting_how_to(normalized, tokens):
        return 'show_recent_accounting_documents'
    if _mentions_receipt_how_to(normalized, tokens):
        return 'add_receipt_or_incoming_invoice'
    if _mentions_invoice_how_to(normalized, tokens):
        return 'create_invoice'

    if resolved_top_level_intent in {'unknown', None} and is_help_like and _mentions_info_help(normalized, tokens):
        return 'overview'

    return None


def _render_product_truth_payload(payload: Mapping[str, Any]) -> str:
    capability_id = str(payload.get('capability_id') or '')
    slovak_copy = _SLOVAK_CAPABILITY_COPY.get(capability_id, {})
    title = str(slovak_copy.get('title') or payload.get('title') or capability_id or 'Neznáma schopnosť')
    product_status = str(payload.get('product_status') or 'unknown')
    account_status = str(payload.get('account_status') or 'unknown')
    summary = str(slovak_copy.get('summary') or payload.get('summary_for_user') or '').strip()
    limitation = str(slovak_copy.get('limitation') or _join_payload_text(payload.get('current_limitations'))).strip()
    safe_next = str(slovak_copy.get('safe_next') or _join_payload_text(payload.get('safe_next_steps'))).strip()

    lines = [
        f'{title}: {_STATUS_LABELS.get(product_status, product_status)}.',
    ]
    if account_status != 'ready':
        lines.append(f'Stav účtu: {_ACCOUNT_STATUS_LABELS.get(account_status, account_status)}.')
    if summary:
        lines.append(summary)
    if limitation:
        lines.append('Obmedzenie: ' + limitation)
    if payload.get('requires_external_credentials'):
        lines.append('Vyžadovalo by to externé prístupy alebo samostatnú integráciu; v aktuálnej verzii to nie je nastavené.')
    if payload.get('dangerous'):
        lines.append('Je to citlivá alebo deštruktívna oblasť, preto musí zostať za deterministickou bezpečnostnou bránou.')
    missing_setup_keys = [str(item) for item in payload.get('missing_setup_keys') or ()]
    if missing_setup_keys:
        lines.append('Chýba nastavenie: ' + ', '.join(missing_setup_keys) + '.')
    if safe_next:
        lines.append('Bezpečný ďalší krok: ' + safe_next)
    review_offer = _human_review_offer_for_payload(payload)
    if review_offer:
        lines.append(review_offer)

    return '\n\n'.join(lines)


def _join_payload_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ' '.join(str(item).strip() for item in value if str(item).strip())
    return ''


def _human_review_offer_for_payload(payload: Mapping[str, Any]) -> str | None:
    if not payload.get('customization_allowed'):
        return None
    product_status = str(payload.get('product_status') or 'unknown')
    if product_status == 'supported':
        return None
    capability_id = str(payload.get('capability_id') or '')
    if capability_id == 'send_invoice_email':
        return (
            'Ak chcete automatické odosielanie faktúr emailom priamo z bota, '
            'môžem z toho pripraviť požiadavku na kontrolu správcom. '
            'Uloží sa iba vtedy, keď ju potvrdíte.'
        )
    return (
        'Ak chcete, môžem z toho pripraviť požiadavku na kontrolu správcom. '
        'Uloží sa iba vtedy, keď ju potvrdíte.'
    )


def _build_capability_overview() -> str:
    capabilities = {capability.capability_id: capability for capability in list_capabilities()}
    lines = ['Overený prehľad podľa Product Truth:']
    for capability_id in _PRODUCT_TRUTH_OVERVIEW_IDS:
        capability = capabilities.get(capability_id)
        if capability is None:
            continue
        status = _STATUS_LABELS.get(capability.status.value, capability.status.value)
        title = _SLOVAK_OVERVIEW_TITLES.get(capability.capability_id, capability.capability_id)
        lines.append(f'- {title}: {status}')
    lines.append('Ak sa pýtate na konkrétnu funkciu, napíšte ju priamo a odpoviem podľa Product Truth.')
    return '\n'.join(lines)


def _normalize_text(text: str) -> str:
    stripped = text.strip().lower()
    without_diacritics = ''.join(
        char for char in unicodedata.normalize('NFKD', stripped) if not unicodedata.combining(char)
    )
    return re.sub(r'[^a-z0-9а-яіїєґ\s]+', ' ', without_diacritics).strip()


def _is_help_like(normalized: str, tokens: set[str]) -> bool:
    return '?' in normalized or bool(tokens.intersection(_HELP_CUES)) or any(
        phrase in normalized for phrase in _OVERVIEW_PHRASES
    )


def _mentions_runtime_issue_intake(normalized: str, tokens: set[str]) -> bool:
    issue_terms = {'problem', 'problemu', 'chybu', 'chyba'}
    report_terms = {'nahlasit', 'nahlasim', 'nahlas', 'ulozit', 'ulozim'}
    help_terms = {'ako', 'vies', 'mozno', 'mozem'}
    return bool(tokens & issue_terms and tokens & report_terms and tokens & help_terms)


def _mentions_email_invoice(normalized: str, tokens: set[str]) -> bool:
    return (
        (tokens.intersection({'email', 'mail', 'gmail'}) or any(token.startswith('email') for token in tokens))
        and tokens.intersection({'fakturu', 'faktura', 'invoice', 'odoslat', 'poslat', 'posli', 'send'})
    )


def _mentions_google_drive(normalized: str, tokens: set[str]) -> bool:
    return (
        ('google' in tokens and ('drive' in tokens or 'disk' in tokens))
        or 'googledrive' in normalized
        or 'google disk' in normalized
    )


def _mentions_google_drive_invoice_archive_after_due_date(normalized: str, tokens: set[str]) -> bool:
    if not _mentions_google_drive(normalized, tokens):
        return False
    mentions_invoice = bool(tokens.intersection({'faktura', 'fakturu', 'faktury', 'faktur', 'invoice', 'invoices'}))
    mentions_archive = bool(
        tokens.intersection({'archiv', 'archivacia', 'archivovat', 'archive', 'upload', 'nahrat', 'ulozit'})
    )
    mentions_followup_context = bool(
        tokens.intersection(
            {
                'splatnosti',
                'splatnost',
                'zaplatena',
                'zaplateni',
                'paid',
                'payment',
                'reminder',
                'pripomienke',
                'pripomienka',
            }
        )
    )
    return mentions_invoice and mentions_archive and mentions_followup_context


def _mentions_invoice_due_date_reminders(normalized: str, tokens: set[str]) -> bool:
    if tokens.intersection({'sms', 'esemes', 'esemesky'}):
        return False
    if tokens.intersection({'adminovi', 'admin', 'spravcovi', 'spravca'}) and tokens.intersection(
        {'povedz', 'posli', 'odosli', 'napis'}
    ):
        return False
    mentions_invoice = bool(tokens.intersection({'faktura', 'fakturu', 'faktury', 'faktur', 'invoice', 'invoices'}))
    mentions_reminder = bool(
        tokens.intersection(
            {
                'pripomienky',
                'pripomienka',
                'pripomenut',
                'pripominat',
                'reminder',
                'reminders',
                'remind',
                'upozornenie',
                'upozornit',
            }
        )
    )
    mentions_due_or_unpaid = bool(
        tokens.intersection(
            {
                'splatnosti',
                'splatnost',
                'neuhradene',
                'neuhradenych',
                'nezaplatene',
                'nezaplatenych',
                'unpaid',
                'overdue',
                'late',
                'due',
            }
        )
    )
    return mentions_invoice and mentions_reminder and mentions_due_or_unpaid


def _mentions_accounting_export(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'export', 'exportovat', 'exportujete'})) and bool(
        tokens.intersection(
            {
                'uctovnictva',
                'uctovnictvo',
                'uctovny',
                'uctovneho',
                'podklady',
                'accounting',
                'pohoda',
                'omega',
            }
        )
    )


def _mentions_custom_pdf_template(normalized: str, tokens: set[str]) -> bool:
    return (
        'pdf' in tokens
        and bool(tokens.intersection({'sablona', 'sablonu', 'template', 'vzor'}))
        and bool(
            tokens.intersection(
                {'stara', 'vlastna', 'vlastnu', 'custom', 'moja', 'moju', 'old', 'upravit', 'zmenit'}
            )
        )
    )


def _mentions_customization_request(normalized: str, tokens: set[str]) -> bool:
    return bool(
        tokens.intersection({'upravu', 'customizaciu', 'customization', 'poziadavku', 'poziadavka', 'vlastnu'})
    ) and bool(
        tokens.intersection({'funkciu', 'feature', 'zmenu', 'request', 'otazku', 'spravcovi', 'kontrolu'})
    )


def _mentions_human_review_request_lifecycle(normalized: str, tokens: set[str]) -> bool:
    mentions_request = bool(tokens.intersection({'poziadavka', 'poziadavku', 'otazka', 'otazku', 'request'}))
    mentions_review = bool(tokens.intersection({'kontrolu', 'review', 'spravcovi', 'spravca', 'adminovi', 'admin'}))
    unknown_question = 'nevie odpovedat' in normalized or 'nevies odpovedat' in normalized or 'nemoze odpovedat' in normalized
    send_to_admin_question = mentions_request and mentions_review and bool(tokens.intersection({'mozem', 'da', 'poslat', 'ulozit', 'ako'}))
    return (
        ('ako funguje' in normalized and mentions_request)
        or unknown_question
        or send_to_admin_question
    )


def _mentions_admin_response_to_user(normalized: str, tokens: set[str]) -> bool:
    mentions_admin = bool(tokens.intersection({'spravca', 'spravcu', 'admin', 'admina'}))
    mentions_answer = bool(tokens.intersection({'odpovie', 'odpoved', 'odpoveda', 'odpovedat', 'response'}))
    return mentions_admin and mentions_answer


def _mentions_admin_review_status(normalized: str, tokens: set[str]) -> bool:
    mentions_request = bool(tokens.intersection({'poziadavka', 'poziadavku', 'request'}))
    mentions_status = bool(tokens.intersection({'prijata', 'prijatu', 'zamietnuta', 'zamietnutu', 'accepted', 'rejected'}))
    return mentions_request and mentions_status and bool(tokens.intersection({'co', 'znamena', 'ako', 'status'}))


def _mentions_admin_response_delivery_observability(normalized: str, tokens: set[str]) -> bool:
    mentions_delivery = bool(tokens.intersection({'dorucena', 'dorucenie', 'dorucit', 'dosla', 'prisla', 'delivery'}))
    mentions_answer = bool(tokens.intersection({'odpoved', 'odpovedi', 'spravcu', 'admina'}))
    return mentions_delivery and mentions_answer and bool(tokens.intersection({'ako', 'zistim', 'vidim', 'stav'}))


def _mentions_access_request_approval(normalized: str, tokens: set[str]) -> bool:
    mentions_access = bool(tokens.intersection({'pristup', 'access', 'schvalenie', 'schvalit', 'povolit'}))
    mentions_admin = bool(tokens.intersection({'spravca', 'admin', 'adminom'}))
    return mentions_access and (mentions_admin or bool(tokens.intersection({'ziadost', 'poziadat', 'ako'})))


def _mentions_code_agent_handoff(normalized: str, tokens: set[str]) -> bool:
    mentions_code_agent = 'code' in tokens and any(token == 'agent' or token.startswith('agent') for token in tokens)
    return (
        mentions_code_agent
        or ('kod' in tokens and 'agent' in tokens)
        or bool(tokens.intersection({'nasadit', 'deploy', 'merge'}))
    )


def _mentions_voice_limit(normalized: str, tokens: set[str]) -> bool:
    if not bool(tokens.intersection({'hlasom', 'voice', 'audio', 'nahovorim', 'diktovat'})):
        return False
    if tokens.intersection({'fakturu', 'faktura', 'invoice', 'iban', 'email', 'cislo', 'suma', 'presne'}):
        return True
    return bool(tokens.intersection({'mozem', 'da', 'ako', 'vies', 'viete'}))


def _mentions_business_profiles(normalized: str, tokens: set[str]) -> bool:
    profile_terms = {'profil', 'profily', 'profile', 'profiles', 'workspace', 'workspaces', 'профіль', 'профілі', 'профиль', 'профили'}
    multi_terms = {'viac', 'dva', 'multiple', 'switch', 'prepnut', 'prepni', 'перемкнути', 'переключить', 'кілька', 'несколько'}
    return bool(tokens.intersection(profile_terms) and tokens.intersection(multi_terms)) or '/profily' in normalized

def _mentions_delete_database_safety(normalized: str, tokens: set[str]) -> bool:
    if not tokens.intersection({'databazu', 'database', 'udaje', 'ucet'}):
        return False
    if not tokens.intersection({'vymaz', 'vymazat', 'vymazem', 'zmaz', 'zmazat', 'zmazem', 'delete', 'odstranit', 'zrusit'}):
        return False
    return bool(tokens.intersection(_HELP_CUES)) or normalized.startswith('ako ')


def _mentions_receipt_how_to(normalized: str, tokens: set[str]) -> bool:
    if not bool(tokens.intersection({'blocek', 'blocky', 'doklad', 'receipt', 'prijatu'})):
        return False
    return bool(tokens.intersection({'ako', 'how', 'pridam', 'nahrat', 'nahram', 'upload'}))


def _mentions_accounting_document_analytics_capability(normalized: str, tokens: set[str]) -> bool:
    document_terms = {
        'prijata',
        'prijate',
        'prijatych',
        'prijatu',
        'incoming',
        'doklad',
        'doklady',
        'dokladov',
        'uctovne',
        'vydavky',
        'vydavkov',
        'naklady',
        'nakladov',
        'minul',
        'minula',
        'minute',
        'spent',
        'expense',
        'expenses',
    }
    invoice_side_terms = {'faktura', 'faktury', 'faktur', 'invoice', 'invoices'}
    analytics_terms = {
        'analytika',
        'analytiku',
        'analyzovat',
        'analyzuj',
        'analytics',
        'analyze',
        'analyza',
        'report',
        'prehlad',
        'vykaz',
        'kolko',
        'pocet',
        'pocitaj',
        'suma',
        'sumy',
        'sucet',
        'ukaz',
        'kategoria',
        'kategorie',
        'kategorii',
        'category',
        'categories',
    }
    incoming_terms = {'prijata', 'prijate', 'prijatych', 'prijatu', 'incoming'}
    receipt_terms = {'blocek', 'blocky', 'blockov', 'receipt', 'receipts', 'cek', 'ceky', 'cekov'}
    if tokens.intersection(incoming_terms) and tokens.intersection(invoice_side_terms):
        return bool(tokens.intersection(analytics_terms))
    if tokens.intersection(receipt_terms):
        return False
    return bool(tokens.intersection(document_terms)) and bool(tokens.intersection(analytics_terms))

def _mentions_accounting_document_categories(normalized: str, tokens: set[str]) -> bool:
    receipt_terms = {
        'blocek',
        'blocku',
        'blocky',
        'blockov',
        'doklad',
        'doklady',
        'receipt',
        'receipts',
        'prijatu',
        'fakturu',
        'invoice',
    }
    category_terms = {
        'kategoria',
        'kategoriu',
        'kategorie',
        'kategorii',
        'kategorizovat',
        'kategorizacia',
        'categorize',
        'categorise',
        'category',
        'categories',
    }
    analytics_terms = {
        'analytika',
        'analytiku',
        'analyzovat',
        'analytics',
        'report',
        'prehlad',
        'vykaz',
        'vydavky',
        'vydavkov',
        'spending',
        'expenses',
    }
    if not (tokens.intersection(receipt_terms) and tokens.intersection(category_terms)):
        return False
    return not bool(tokens.intersection(analytics_terms))


def _mentions_receipt_analytics_capability(normalized: str, tokens: set[str]) -> bool:
    receipt_terms = {
        'blocek',
        'blocky',
        'blockov',
        'doklad',
        'doklady',
        'receipt',
        'receipts',
        'cek',
        'ceky',
        'cekov',
        'чеки',
        'чеків',
        'чеков',
        'чеках',
    }
    analytics_terms = {
        'analytika',
        'analytiku',
        'analyzovat',
        'analyzuj',
        'analytics',
        'analyze',
        'analyza',
        'report',
        'prehlad',
        'vykaz',
        'vydavky',
        'vydavkov',
        'kategoria',
        'kategorie',
        'kategorii',
        'kategorizovat',
        'kategorizacia',
        'category',
        'categories',
        'spending',
        'expenses',
        'витрат',
        'витрати',
        'категорії',
        'категоріі',
        'категорія',
        'категории',
        'категория',
        'аналітика',
        'аналитика',
        'аналіз',
        'анализ',
    }
    return bool(tokens.intersection(receipt_terms)) and bool(tokens.intersection(analytics_terms))


def _mentions_bank_cashflow_tax_analytics(normalized: str, tokens: set[str]) -> bool:
    domain_terms = {
        'banka',
        'banku',
        'bankove',
        'bankovy',
        'cashflow',
        'cash',
        'dph',
        'vat',
        'dan',
        'dane',
        'danovy',
        'danovu',
        'danovo',
        'danove',
        'danova',
        'uznatelne',
        'uznatelny',
        'uznatelna',
        'bankovymi',
        'bankovych',
        'pohyb',
        'pohyby',
        'pohybmi',
        'tax',
        'bank',
        'банку',
        'банк',
        'банкові',
        'ндс',
        'пдв',
        'налог',
        'налоги',
        'податок',
        'податки',
    }
    analytics_terms = {
        'analytika',
        'analyzovat',
        'analytics',
        'report',
        'prehlad',
        'vykaz',
        'vypocet',
        'cashflow',
        'analyza',
        'аналітика',
        'аналитика',
        'аналіз',
        'анализ',
        'звіт',
        'отчет',
    }
    return bool(tokens.intersection(domain_terms)) and (
        bool(tokens.intersection(analytics_terms))
        or bool(tokens.intersection({'vies', 'viete', 'mozes', 'mozete', 'can', 'could', 'da'}))
    )


def _mentions_recent_accounting_how_to(normalized: str, tokens: set[str]) -> bool:
    mentions_docs = bool(tokens.intersection({'blocek', 'blocky', 'blockov', 'doklady', 'dokladov', 'uctovne'}))
    mentions_recent = bool(tokens.intersection({'posledne', 'nedavne', 'recent', 'zobrazim', 'ukazem', 'ako'}))
    return mentions_docs and mentions_recent and not tokens.intersection({'pridam', 'nahrat', 'nahram', 'upload'})


def _mentions_contact_how_to(normalized: str, tokens: set[str]) -> bool:
    mentions_contact = bool(
        tokens.intersection(
            {'kontakt', 'contact', 'odberatela', 'zakaznika', 'firmu', 'firmy', 'spolocnost'}
        )
    )
    mentions_action = bool(
        tokens.intersection(
            {'ako', 'pridam', 'vytvorim', 'ulozim', 'vyhladam', 'vyhladat', 'najdem', 'hladat', 'ico', 'register', 'registri'}
        )
    )
    return mentions_contact and mentions_action

def _mentions_service_alias_how_to(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'sluzbu', 'sluzba', 'polozku', 'polozka', 'alias'})) and bool(
        tokens.intersection({'ako', 'pridam', 'vytvorim', 'ulozim'})
    )


def _mentions_edit_existing_invoice_how_to(normalized: str, tokens: set[str]) -> bool:
    mentions_invoice = bool(tokens.intersection({'fakturu', 'faktura', 'invoice'}))
    mentions_edit = bool(tokens.intersection({'upravim', 'upravit', 'edit', 'zmenim', 'zmenit'}))
    return mentions_invoice and mentions_edit and bool(tokens.intersection({'ako', 'mozem', 'da'}))



def _mentions_work_time_tracking(normalized: str, tokens: set[str]) -> bool:
    work_terms = {
        'pracovneho', 'pracovny', 'pracovny', 'hodiny', 'hodin', 'dochadzka', 'vykaz', 'casu',
        'time', 'hours', 'obed', 'obedna', 'obednu', 'obednej', 'prestavka', 'prestavku', 'prest?vka',
        'prest?vku', 'break', 'lunch',
    }
    payroll_terms = {'mzdu', 'mzdova', 'vyplatu', 'payroll', 'salary'}
    export_terms = {'export', 'exportovat', 'uctovnicke', 'softveru'}
    lunch_terms = {'obed', 'obedna', 'obednu', 'obednej', 'prestavka', 'prestavku', 'prest?vka', 'prest?vku', 'break', 'lunch'}
    if tokens.intersection(payroll_terms) or tokens.intersection(export_terms):
        return bool(tokens.intersection({'dochadzka', 'hodiny', 'hodin', 'pracovneho'}))
    if tokens.intersection(lunch_terms):
        return bool(tokens.intersection({'vie', 'vies', 'viete', 'ako', 'mozem', 'da', 'nastavit', 'zmenit', 'zmenim', 'odpocitat'}))
    return bool(tokens.intersection(work_terms)) and bool(tokens.intersection({'vie', 'vies', 'viete', 'ako', 'mozem', 'da', 'hlasom', 'vytvorim', 'evidovat'}))
def _mentions_mark_existing_invoice_paid(normalized: str, tokens: set[str]) -> bool:
    mentions_invoice = bool(tokens.intersection({'fakturu', 'faktura', 'faktury', 'invoice'}))
    mentions_mark = bool(tokens.intersection({'oznac', 'oznacit', 'poznac', 'poznacit', 'mark'}))
    mentions_paid = bool(tokens.intersection({'uhradenu', 'uhradena', 'uhradene', 'zaplatenu', 'zaplatena', 'paid'}))
    help_like = bool(tokens.intersection({'ako', 'mozem', 'da', 'vies', 'viete'})) or '?' in normalized
    return mentions_invoice and mentions_mark and mentions_paid and help_like


def _mentions_delete_existing_invoice_how_to(normalized: str, tokens: set[str]) -> bool:
    mentions_invoice = bool(tokens.intersection({'fakturu', 'faktura', 'invoice'}))
    mentions_delete = bool(tokens.intersection({'vymazem', 'vymazat', 'zmazem', 'zmazat', 'delete', 'odstranit'}))
    return mentions_invoice and mentions_delete and bool(tokens.intersection({'ako', 'mozem', 'da'}))


def _mentions_invoice_how_to(normalized: str, tokens: set[str]) -> bool:
    if not tokens.intersection({'fakturu', 'faktura', 'invoice'}):
        return False
    if bool(tokens.intersection(_DIRECT_ACTION_GUARD_WORDS)):
        return False
    return bool(tokens.intersection({'ako', 'how'})) or 'ako vytvorim' in normalized or 'how do i create' in normalized


def _mentions_info_help(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'pomoc', 'help', 'funkcie', 'capabilities'})) or any(
        phrase in normalized for phrase in _OVERVIEW_PHRASES
    )


def _known_capability_ids() -> tuple[str, ...]:
    return tuple(capability.capability_id for capability in list_capabilities())


def _bounded_text(value: object, *, max_length: int) -> str:
    if not isinstance(value, str):
        return ''
    compacted = re.sub(r'\s+', ' ', value).strip()
    if len(compacted) <= max_length:
        return compacted
    return compacted[: max_length - 1].rstrip() + '…'


def _bounded_choice(value: object, *, allowed: tuple[str, ...], default: str) -> str:
    candidate = str(value or '').strip()
    if candidate in allowed:
        return candidate
    return default


def _bounded_text_list(value: object, *, max_items: int, max_length: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    items: list[str] = []
    for item in value:
        clean = _bounded_text(item, max_length=max_length)
        if clean:
            items.append(clean)
        if len(items) >= max_items:
            break
    return tuple(items)

def _bounded_confidence(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if parsed < 0:
        return 0.0
    if parsed > 1:
        return 1.0
    return parsed


def _triage_result(
    triage_class: str,
    *,
    confidence: float,
    needs_clarification: bool = False,
    business_need: str = '',
) -> InfoHelpTriageResult:
    return InfoHelpTriageResult(
        topic_id=_TRIAGE_TOPIC_BY_CLASS.get(triage_class, TRIAGE_UNKNOWN),
        triage_class=triage_class,
        confidence=confidence,
        needs_clarification=needs_clarification,
        business_need=business_need,
    )


def _is_noise_or_abuse(normalized: str, tokens: set[str]) -> bool:
    if not tokens:
        return True
    if len(normalized) <= 2:
        return True
    alpha_count = sum(1 for char in normalized if char.isalpha())
    if alpha_count == 0:
        return True
    return normalized in {'asdf', 'qwerty', 'bla bla bla'}


def _is_smalltalk(normalized: str, tokens: set[str]) -> bool:
    return (
        normalized in {'ako sa mas', 'ako sa mate', 'how are you', 'jak sa mas'}
        or ('ako' in tokens and 'mas' in tokens and len(tokens) <= 4)
        or ('справи' in tokens and len(tokens) <= 4)
        or ('дела' in tokens and len(tokens) <= 4)
    )


def _is_unclear_request(normalized: str, tokens: set[str]) -> bool:
    return normalized in {
        'urob mi to',
        'sprav mi to',
        'zrob mi to',
        'urob to',
        'sprav to',
        'do it',
        'зроби це',
        'сделай это',
    } or (tokens.intersection({'urob', 'sprav', 'zrob', 'сделай', 'зроби'}) and tokens <= {
        'urob',
        'sprav',
        'zrob',
        'mi',
        'to',
        'сделай',
        'зроби',
        'це',
        'это',
    })


def _is_out_of_domain(normalized: str, tokens: set[str]) -> bool:
    return bool(tokens.intersection({'pocasie', 'weather', 'forecast', 'погода', 'погоду'}))


def _is_admin_review_request(normalized: str, tokens: set[str]) -> bool:
    mentions_admin = bool(tokens.intersection({'adminovi', 'admin', 'spravcovi', 'spravca', 'админу', 'адміну'}))
    return mentions_admin and bool(
        tokens.intersection({'povedz', 'posli', 'odosli', 'napis', 'potrebujem', 'скажи', 'передай'})
    )


def _is_new_business_feature_request(normalized: str, tokens: set[str]) -> bool:
    if _is_invoice_period_summary_request(normalized, tokens):
        return False
    if _is_invoice_analytics_request(normalized, tokens):
        return False
    mentions_revenue_overview = bool(tokens.intersection({'trzieb', 'trzby', 'revenue', 'vynosov', 'выручки', 'виручки'})) and bool(
        tokens.intersection({'prehlad', 'report', 'vykaz', 'overview', 'отчет', 'звіт'})
    )
    mentions_month = bool(tokens.intersection({'mesiac', 'mesacny', 'monthly', 'месяц', 'місяць'}))
    return mentions_revenue_overview or (
        mentions_month
        and bool(tokens.intersection({'prehlad', 'report', 'vykaz', 'overview', 'отчет', 'звіт'}))
        and not tokens.intersection({'fakturu', 'faktura', 'invoice'})
    )


def _is_invoice_period_summary_request(normalized: str, tokens: set[str]) -> bool:
    month_terms = {
        'mesiac',
        'mesiace',
        'mesiacov',
        'month',
        'monthly',
        'marec',
        'marci',
        'march',
        'maj',
        'maji',
        'may',
        '\u043c\u0456\u0441\u044f\u0446\u044c',
        '\u043c\u0456\u0441\u044f\u0446\u044f\u0445',
        '\u043c\u0456\u0441\u044f\u0446\u044f\u043c\u0438',
        '\u043c\u0435\u0441\u044f\u0446',
        '\u0431\u0435\u0440\u0435\u0437\u0435\u043d\u044c',
        '\u0431\u0435\u0440\u0435\u0437\u043d\u0456',
        '\u0442\u0440\u0430\u0432\u0435\u043d\u044c',
        '\u0442\u0440\u0430\u0432\u043d\u0456',
    }
    if tokens.intersection(month_terms):
        return False
    invoice_terms = {
        'faktura',
        'fakturu',
        'faktury',
        'faktur',
        'invoice',
        'invoices',
        'фактуру',
        'фактура',
        'фактуры',
        'фактури',
        'фактур',
    }
    report_terms = {
        'suma',
        'sumu',
        'celkom',
        'spolu',
        'kolko',
        'suhrn',
        'suhrny',
        'prehlad',
        'report',
        'vykaz',
        'summary',
        'total',
        'amount',
        'сума',
        'суму',
        'сумму',
        'сколько',
        'кольки',
        'звіт',
        'звит',
        'отчет',
        'отчёт',
        'усяго',
        'всего',
    }
    issued_terms = {
        'vystavil',
        'vystavene',
        'vystavenych',
        'issued',
        'створив',
        'виставив',
        'виставіў',
        'выставил',
        'выставіў',
        'выставі',
        'выставленных',
    }
    period_terms = {
        'rok',
        'roku',
        'rocne',
        'year',
        'yearly',
        'tento',
        'tomto',
        'obdobie',
        'obdobi',
        'місяць',
        'месяц',
        'год',
        'году',
        'році',
        'роцы',
        'годзе',
    }
    return (
        bool(tokens.intersection(invoice_terms))
        and bool(tokens.intersection(report_terms))
        and (
            bool(tokens.intersection(issued_terms))
            or bool(tokens.intersection(period_terms))
            or bool(re.search(r'\b(?:19|20)\d{2}\b', normalized))
        )
    )


def _mentions_invoice_period_summary_capability(normalized: str, tokens: set[str]) -> bool:
    capability_question_terms = {
        'vie',
        'vies',
        'viete',
        'mozes',
        'mozete',
        'dokazes',
        'dokazete',
        'da',
        'ako',
        'how',
        'can',
        'could',
    }
    return _is_invoice_period_summary_request(normalized, tokens) and bool(
        tokens.intersection(capability_question_terms)
    )


def _is_invoice_analytics_request(normalized: str, tokens: set[str]) -> bool:
    if _is_invoice_period_summary_request(normalized, tokens):
        return False
    invoice_terms = {
        'faktura',
        'fakturu',
        'faktury',
        'faktur',
        'invoice',
        'invoices',
        'фактуру',
        'фактура',
        'фактуры',
        'фактури',
        'фактур',
    }
    analytics_terms = {
        'analytika',
        'analytiku',
        'analytics',
        'report',
        'prehlad',
        'vykaz',
        'porovnaj',
        'porovnanie',
        'compare',
        'mesiac',
        'mesacny',
        'month',
        'maj',
        'may',
        'top',
        'najviac',
        'priemer',
        'priemerna',
        'average',
        'neuhradene',
        'neuhradenych',
        'nezaplatene',
        'nezaplatenych',
        'zaplatene',
        'uhradene',
        'unpaid',
        'paid',
        'klienti',
        'zakaznici',
        'odberatelia',
        'customers',
        'trzby',
        'obrat',
        'сравни',
        'порівняй',
        'травень',
        'май',
        'топ',
        'клієнтів',
        'клиентов',
        'неоплачених',
        'неоплачені',
        'оплачені',
        'середня',
        'средняя',
        'оборот',
    }
    return bool(tokens.intersection(invoice_terms)) and bool(tokens.intersection(analytics_terms))


def _mentions_invoice_analytics_capability(normalized: str, tokens: set[str]) -> bool:
    capability_question_terms = {
        'vie',
        'vies',
        'viete',
        'mozes',
        'mozete',
        'dokazes',
        'dokazete',
        'da',
        'ako',
        'how',
        'can',
        'could',
    }
    return _is_invoice_analytics_request(normalized, tokens) and (
        bool(tokens.intersection(capability_question_terms))
        or 'analytika' in tokens
        or 'analytics' in tokens
    )


def _is_customization_candidate(normalized: str, tokens: set[str]) -> bool:
    if bool(tokens.intersection({'automaticke', 'automaticky', 'automatic', 'автоматичні', 'автоматические'})) and bool(
        tokens.intersection({'pripomienky', 'reminders', 'напоминания', 'нагадування'})
    ):
        return True
    return bool(tokens.intersection({'potrebujem', 'chcem', 'хочу', 'потрібно'})) and bool(
        tokens.intersection({'upravu', 'prisposobit', 'custom', 'vlastne', 'vlastnu', 'zmenu'})
    )


def _is_possible_product_truth_candidate(normalized: str, tokens: set[str]) -> bool:
    if not _is_help_like(normalized, tokens):
        return False
    return bool(
        tokens.intersection(
            {
                'faktura',
                'fakturu',
                'faktury',
                'invoice',
                'pdf',
                'kontakt',
                'doklad',
                'blocky',
                'uctovnictvo',
                'uctovne',
                'sluzby',
                'profil',
            }
        )
    )


def build_top_level_unknown_guidance(*, user_input_text: str | None = None) -> str:
    """Build deterministic Phase 1 guidance for idle top-level unknown input."""
    return (
        'Nerozumiem, čo chcete spraviť.\n\n'
        'Môžem vám pomôcť napríklad s týmito vecami:\n'
        '- vytvoriť faktúru,\n'
        '- zobraziť alebo upraviť existujúcu faktúru,\n'
        '- spočítať súhrn vystavených faktúr za kalendárny rok,\n'
        '- pridať kontakt,\n'
        '- upraviť môj profil,\n'
        '- pridať službu používanú vo faktúrach,\n'
        '- pridať bloček alebo prijatú faktúru.\n\n'
        'Skúste napísať konkrétne, čo chcete urobiť, napríklad „vytvor faktúru“, '
        '„súhrn faktúr za 2026“, „pridaj kontakt“ alebo „pridaj bloček“.'
    )
