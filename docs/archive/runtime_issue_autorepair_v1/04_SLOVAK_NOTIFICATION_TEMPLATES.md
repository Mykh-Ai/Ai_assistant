# Runtime Issue Workshop — Slovak Notification Templates

Tone: concise, factual, business Slovak. No promise of repair timing. No claim of code, data, merge, deployment, external upload, or rollback unless verified.

## Diagnosis split

```text
Hlásenie {issue_id} bolo analyzované a rozdelené na {finding_count} samostatné pracovné položky:

{numbered_results}

Podrobnosti boli uložené v internom servisnom zázname.
```

## Example result lines

```text
1. Pri položke {finding_id} bola potvrdená potreba samostatného návrhu architektúry. Kód ani produkcia neboli zmenené.
```

```text
2. Položka {finding_id} bola zaradená do radu na bezpečnú opravu.
```

```text
3. Pri položke {finding_id} boli zistené neaktuálne údaje. Automatická zmena produkčných údajov nebola vykonaná; položka vyžaduje autorizovanú opravu údajov.
```

## Draft PR ready

```text
Pre položku {finding_id} bola pripravená oprava na kontrolu.
Draft PR: {pr_reference}
Commit: {short_commit_sha}
Produkcia nebola zmenená.
```

## Expected behavior

```text
Položka {finding_id} bola overená ako očakávané správanie podľa aktuálnych pravidiel produktu.
Kód ani produkcia neboli zmenené.
```

## External failure

```text
Pri položke {finding_id} bola potvrdená externá technická príčina.
Kód ani produkcia neboli zmenené.
```

## Insufficient evidence

```text
Položku {finding_id} sa nepodarilo spoľahlivo diagnostikovať z dostupných údajov.
Kód ani produkcia neboli zmenené.
```

## Nightly summary

```text
Nočné servisné spracovanie bolo dokončené.
Prevzaté hlásenia: {received_count}
Nové pracovné položky: {finding_count}
Opravy pripravené na kontrolu: {draft_pr_count}
Položky prenesené do ďalšieho spracovania: {carry_forward_count}
Produkcia nebola zmenená.
```

Do not send a nightly summary when nothing was received, changed, blocked, or carried forward and no notification is useful.
