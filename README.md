# FVE Load Control for Home Assistant

Integrace pro řízení spotřeby domu pro minimalizaci přetoků do sítě.

> Projekt je v ranné fázi vývoje a je to moje první custom integrave pro Home Assitant, takže není krásná jak jsem se učil. Ačkoliv mi funguje dobře, berte ji jako alfa verzi. Uvítám zpětnou vazbu jak jede na vašich FVE - optimálně formou issues. 

## Motivace

Podívejme se na reálnou situaci ze https://solar-assistant.io. Žlutá je výkon FVE, modrá spotřeba domu, červená odběr / přetoky do sítě.
![](./imgs/2023-05-31-20-37-33.png)

V 9:40 již svítilo tolik, že začaly přetoky. Spotřeba domu byla cca. 266W. Automatika spustila v 10.00 dobíjení auta (cca. 2200W navíc). Následně zvyšovala výkon autonabíječky až na 3200W. Odpoledne postupně výkon snižovala. v 15:48 se již auto nabilo a současně byla plná baterie FVE. Automatika spustika cryptominer se spotřebou cca. 1500W, který běžel do cca. 1700W, kdy už klesl výkon a současně vzrostla spotřeba.

Pokud by k tomuto nedocházelo bude spotřeba vypadat stále jako cca. 200 - 300W. Někdy kolem 11.00 by se plně nabila baterie a zbytek dne by se vše vyváželo do sítě.

Díky této automatizaci se mi daří dlouhodobě držet velmi vysoký podíl doma spotřebované solární energie. Kolem 90% za měsíc květen.

![](./imgs/2023-05-31-20-46-17.png)


## Princip fungování

Princip je velmi prostý. Integrace si na vstupu bere informace z FVE (v mém případě Solar Assistant, ale je to obecné). Spotřebu, výkon panelů, nabití baterie, nákup / prodej do sítě. Na základě těchto dat si v každý okamžik počítá kolik je výkonu navíc k dispozici. 

Všechny veličiny si zprůměruje za posledních 10minut abyhchom se vyhli unáhlené reakci na výkyvy způsobené např. mraky apod.

Následně si spočítá **kolik je výkonu navíc**. K tomu používá tři strategie:

1) **Minimální** je prostě rovna přetokům. Tedy pokud do sítě teče 500W, snaží se najít zdroj právě s touto energií a zapnout jej.
2) **Střední** je rovna hodnotě, kdy by se vyrovnaly přetoky a současně by se zastavilo nabíjení baterie. To má reálně smysl například ráno, když slunce stoupá a očekáváme jasno. Spustí se zátěž, nabíjení baterie se na chvíli zastaví či zpomalí a pak zase postupně nabíhá.
3) **Maximální** považuje za volný výkon navíc i vybíjecí výkon baterie. Tedy vše co máme k dispozici aby se nazačalo nakupovat z gridu. 

Pokud detekujeme nějaký výkon navíc, postupně se dle priority pokouší zapnout spotřebiče dokud se hodnota extra výkonu nesníží tak, že žádný zdroj nejde spustit. 

---

### Příklad
Máme jen jeden zdroj a to patronu v bojleru s příkonem 2kW.
Panely dávají 2500W, ale postupně se nabíjí baterie výkonem 2kW.  
Spotřeba domu je 100W. Takže máme 400W přetoky.

S **minimální** strategií systém počká do nabití baterie. Dokud se nabíjí je výkon navíc jen 400W. A nejmenší dostupný spotřebič má 2kW. Takže nic.
Najednou se baterie nabije na 100%. V systému tedy máme najenou volných 2400W, které jdou do přetoků. Systém pouští ohřev a volný výkon klesá na 400W. Není k dispozici žádný další spotřebiče menší než 400W, takže se nic neděje.

Se **střední** strategií systém systém vidí jako volný vákon 2kW do baterie a těch 400W přetoků. pouští patronu a tím klesá nabíjecí výkon baterie na 400W. Ta se nabíjí pomaleji, ale stále to jede.

---

Úplně stejně pracujeme pokud naopak výkon chybí. Tedy je spotřeba větší než výkon panelů.

I zde zde bereme několik možností:
- **minimální** strategie vypíní dokud se neukončí nákup a neobnoví nabíjení baterie na max (pokud není nabitá)
- **střední** startegie vypíná dokud se neukončí nákup a baterie nepřestane vybíjet
- **maximální** jen ukončí nákup ze sítě.

Pokud je v systému chybějící výkon, systém zkouší vypnout spotřebiče. Zde bere ohled na definovanou minimální dobu běhu, kterou lze definovat.

A to je vše. V budoucnu plánuji zohlednit předpověď výkonu a počasí a také stav nabití baterie. Tedy trochu jinak reagovat když je baterie prázdná apod. Mám k tomu mnoho připeraveno, ale zatím ve vývojové verzi. I ten výše popsaný jednoduchý systém docela dobře funguje.

Integrace samotná spotřebiče nespouští. Jen posílá do HomeAssistant eventy, které je možné požít pro jejich spuštění automatizací nebo jinou reakci.

## Instalace
Instalace je nejlépo mocí HACS. Je nutné přidat toto REPO
TODO: popsat více

## Konfigurace
Integrace nemá vlastní rozhraní je nutné editovat `configuration.yaml`
Zde je ukázka. Kamkoliv do souboru přidejte něco takovéhoto.

```yaml
fve_control:
  fve_grid_power_sensor: sensor.grid_power
  fve_pv_power_sensor: sensor.pv_power
  fve_load_power_sensor: sensor.load_power
  fve_battery_power_sensor: sensor.battery_power
  fve_battery_soc_sensor: sensor.battery_state_of_charge

  fve_battery_capacity: 10000
  fve_battery_soc_min: 20
  fve_battery_max_power_in: 1900
  fve_battery_max_power_out: 1900
  
  appliances:
    - name: wallbox
      type: wallbox
      max_power: 3650
      min_power: 1800
      step_power: 230
      availability_sensor: binary_sensor.wallbox_charging_available
      switch_sensor: switch.wallbox_gen_2_10_0_30_9_charging_switch
      power_sensor: sensor.wallbox_gen_2_10_0_30_9_power_estimated
      static_priority: 50
      minimal_running_minutes: 30
      startup_time_minutes: 2

    - name: miner1
      type: constant_load
      min_power: 1500
      static_priority: 20
      availability_sensor: binary_sensor.miner_is_available
      switch_sensor: switch.lidl_plug_2
      minimal_running_minutes: 5
      startup_time_minutes: 5

    - name: kola
      type: constant_load
      min_power: 100
      static_priority: 10
      minimal_running_minutes: 0
      availability_sensor: binary_sensor.kola_is_available
      switch_sensor: switch.shelly_220_switch_garaz_switch_2
      power_sensor: sensor.shelly_220_switch_garaz_switch_1_power
      startup_time_minutes: 0
```

První část definuje vstupy z FVE

| parametr | význam |
|----------| ---    |
|   fve_grid_power_sensor    |  entita home assistant ukazující aktuální odběr/přetoky ve Wattech. Pokud jsou přetoky je hodnota záporná jinak kladná  |
|   fve_pv_power_sensor    |  senzor aktuálního výkonu panelů. [W]   |
|   fve_load_power_sensor    |  senzor aktuální celkové spotřeby  [W]|
|   fve_battery_power_sensor    | senzor výkonu z / do baterie. Pokud se baterie nabíjí je hodnota kladná, pokud vybíjí je záporná   [W] |
|   fve_battery_soc_sensor    | procento nabití baterie. Celé číslo 0 až 100  |

Pokud používáte SolarAssistant je konfigurace přesně jako na příkladu. Pokud ne je možné vyrobit virtuální senzory, které jednotky přizpůsobí.

Další částí je základní nastavení systému.

| parametr | povinný |význam |
|----------| --- |---    |
|fve_battery_capacity|ano| celková kapacita baterie we [Wh]|
|fve_battery_soc_min|ano| minimální prcento, kam se vybíjí (0 až 100)|
|fve_battery_max_power_in|ano| jaký je maximální výkon nabíjení baterie [W]|
|fve_battery_max_power_out|ano| jaký je maximální výkon vybíjení baterie [W]|
|treshold_power |ne| minimální hodnota, kdy systém zkouší něco vypínat nebo zapínat. Default: 100W [W]|
|force_stop_power |ne| Hodnota, kdy systém vypíná bez ohledu na minimální časy běhu. Default: 1000W [W]|
|update_interval_sec |ne| interval update senzorů [sec]. Default 10sec|
|decision_interval_sec |ne| interval rozhodování o spuštění / vypnutí [sec]. Default 60sec |
|history_in_minutes |ne |délka historie pro výpočet průměrů hodnot [min]. Default 10min|
|analytics |ne | `true` nebo `false`. Povolí zasílání dat pro statistiky. Default `true` |

A následuje definice spotřebičů. Jsou k dispozici dva typy:
- **constant_load** je spotřebič s neregulovatelným příkonem.
- **wallbox** je spotřebič s regulovatelným příkonem. Zatím jej nazývám takto, do budoucna plánuji odděli wallbox a variable_load s tím, že wallbox by uvažoval i nějaká data z auta.

| parametr | povinný | význam |
|----------| ---    | --- |
|name|ano| název zařízení |
|type|ano| typ. Hodnota `wallbox` nebo `constant_load` |
|min_power|ano| minimální očekávaný výkon [W]|
|max_power|jen pro wallbox| maximální možný výkon [W]|
|step_power|jen pro wallbox| krok zvětšení výkonu [W]|
|availability_sensor|ano| binary senzor, který indikuje zda je spotřebič dostupný a je chtěný jeho start. Příklad: wallbox je dostupný pokud není auto vybité a je vůbec v připojené. Klimatizace je dostupná pokud je v bytě nad 26 stupňů apod. Doporučuji si na toto udělat template senzory. Příklad dále.  |
|switch_sensor|ano| senzor, který indikuje zapnutí vypnutí. Zde je důležité aby indikoval skutečně zapnutí na spotřebu. Tedy u wallboxu zapnutí do stavu charging apod. Ne pohotovostní mód bez odběru. Může se jednat o switch nebo binary senzor. Očekávané hodnoty jsou "on" / "off"|
|power_sensor|ne| pokud je možné, tak senzor, který ukazuje skutečný příkon zapnutého spotřebiče ve wattech. Pokud není vyplněno snaží se komponenta příkon odhadnout z hodnoty minimálního příkonu. Ale to je pochopitelně nouzová varianta a zhoršuje rozhodování. |
|static_priority|ano| priorita. Systém zkouší zapnout ten s nejvyšší prioritou a naopak vypíná jako první ten s nejnižčí. Celé číslo, doporučuji nula až sto|
|minimal_running_minutes|ne| Minimální doba po kterou má spotřebič běžet. |
|startup_time_minutes|ne| Očekávaná doba za jakou má naběhnout na plný výkon. Vhodné třeba u kryptominerů, kdy se pár minut bootuje |

Jakmile toto nakonfigurujete a zrestartujete HA, měli je vše připraveno. Poznáte to dle řady nových senzorů

### Analytika
Parametr `analytics` umožní posílat data do google cloudu k další analýze. Je defaulně zapnutý. Data sbírám jen pro účely zlepšování - moje zkušenosti vycházejí jen z jedné malé FVE, takže mne zajímá jak se chovají jiné.

Co analytika sbírá:
- název home assistantu a lokaci pro rozlišení
- ip adresu 
- data z FVE senzorů 
- informace o rozhodnutí vypnout / zapout spotřebič

Data nikomu nepředávám a po analýze je mažu. Občas je promažu stejně.

### Příklady sensor_available
Proč vlastně používám `availability_sensor`? Určuje, zda je vůbec danný extra spotřebič vhodný ke spuštění. Typicky se jedná o tyto kontroly:
- je vůbec dostupný home assistantovi? Není třeba jeho switch **unavailable**? 
- je vhodné jej spustit? Například auto už může být nabité nebo mimo dům. Voda může být ohřatá. Klimatizaci chcete spustit jen když je v místnosti více než 25C apod.

Proto je potřeba pro každý spotřebič tento senzor definovat. Doporučuji:
- použít template sensor pro kontroly
- nebo použít toggle pro manuálně nastavovaný on/off

Příklad binary senzoru available pro wallbox v `configuration.yaml`

```yaml
template:
  - binary_sensor:
      - name: Wallbox charging available
        unique_id: wallbox_charging_available
        state: >
            {% set wallbox_state = states("sensor.wallbox_gen_2_10_0_30_9_state") %}
            {% set car_battery_soc = states("sensor.tucson_ev_battery_level") | int %}
            
            {% if 
                (
                   wallbox_state == "connect" or 
                   wallbox_state == "finished" or 
                   wallbox_state == "charging"
                 ) and (
                   car_battery_soc < 100
                 )
            %}
            true
            {% else %}
            false
            {% endif %}

```

## Senzory a další prvky
Componenta do HA přidá řadu nových entit.

![](./imgs/2023-05-31-22-14-20.png)

- podstatné je input number `extra_load_priority` nastavuje jakou hodnoty free energie budeme uvažovat. 1 je ta minimální (konzervativní), 3 je střední, 5 je maximum. Hodnoty 2 a 4 jsou průměry mezi. Jako default je 2. Toto číslo do budoucna plánuji dynamicky měnit dle situace. Zatím jej můžete nechat na 2 a nebo měnit nějakou automatizací. Například dopoledne při baterii nad 50% dát agresivnější a odpoledne vrárit na 2 či jedna.

- dle něj se pak vybírá `sensor.free_power_for_decision`
- aktuální odhadovaná hodnota spuštěného výkonu navíc je `sensor.fve_control_extra_load_power` a seznam zapnutých spotřebičů je `sensor.free_extra_load_names`, Je třeba si uvědomit, že alokovaná energie je pouze odhadovaná. Používá se k tomu informace ze senzorů spotřebičů (pokud je) a pokud není, tak nastavená minimální hodnota odběru.

- dále jsou tam různé senzory, které vytvářejí statistiky ze vstupních hodnot (průměr, odchylka, ...). Tyto statistiky se počítají za dobu dle konfigurace. Pokud je doba historie 10minut a interval update je 10 sec, bude se počítat klouzavý průměr z 60-ti hodnot. Pokud se historie zkrátí bude systém reagovat "rychleji" na změny

- také řady kalkulovaných metrik, které se mohou hodit pro automatizace (doba do nejvyšího výkonu, chybějící Wh v baterii a doba do plného nabití atd.)

Do detailu další popíši později nejsou úplně potřeba.

Extra load priority je ale klíčová hodnota

|hodnota| kolik výkonu se snažíme udat pokud svítí | kolik se snaží naopak získat vypínáním| použití |
|---|---|---|---|
|1| jen hodnotu přetoků| co nejvíce bude vypínat. Jednak aby se nenakupovalo z gridu a poté aby se na max nabíjela baterie | Konzervativní nastavení. Neovlivňuje nijak nabíjení baterie. Ale asi bude docházet k přetokům ale baterie bude nejvíce a nejrychleji nabitá. Vhodný na konci dne. |
|2| průměr mezi 1 a 3| ||
|3|přetoky nabíjecí výkon baterie | systém se pokusí uvolnit tolik výkonu aby se zastavilo případné vybíjení baterie a vynuloval nákup z gridu | Nabíjení baterie se může zastavit. Vhodné pokud je baterie dost nabitá a máme před sebou ještě dlouhý a hezký den. |
|4| průměr mezi 3 a 5|||
|5| přetoky + nabíjení baterie + maximální vybíjení baterie | jen omezí nákup z gridu | Režim vybíjí baterii. Má smysl pokud víme, že bude hodně svítit a baterii znovu nabijeme na max |

Do budoucna plánuji přidat chytré rozhodování o těchto režimech na základě stavu baterie, fázi výroby apod.


## Nastavení vypínání a zapínání spotřebičů
Jak jsem psal - tato komponenta přímo sama od sebe spotřebiče neovládá. Pokud usoudí, že je třeba něco vypnout / zapnout prostě pošle do HA event `fve_control`.

![](./imgs/2023-05-31-23-03-10.png)

V datech eventy je uvedeno:
- spotřebič (name)
- akce k provedení. Ta nabývá hodnot: 
  - start
  - stop
  - increase
  - decrease
  - minimum
  - maximum

Start stop jsou asi jasné. Ostatní jsou pro spotřebiče typu wallbox. Jedná se o pokyn ke zvýšení / snížení výkonu o jeden stupeň a nebo nastavení na maximum či minimum.

Pro každou zátěž musíte vytvořit několik automatizací. Minimálně start / stop. 

Ukázka automatizace pro start.

```yaml
alias: FVE-CONTROL > MINER START
description: ""
trigger:
  - platform: event
    event_type: fve_control
    event_data:
      appliance_name: miner1
      action: start
condition:
  - condition: device
    type: is_off
    device_id: c50340caee80f390b0fe8b32326c0a21
    entity_id: switch.lidl_plug_2
    domain: switch
action:
  - type: turn_on
    device_id: c50340caee80f390b0fe8b32326c0a21
    entity_id: switch.lidl_plug_2
    domain: switch
mode: single
```

## Checklist přidání nového spotřebiče
Na konec jen checklist pro přidání nového spotřebiče.

- připravit availability sensor
- připravit automatizace start/stop/...
- přidat do `fve_control` elementu v `configuration.yaml`

## Debug
pokud chcete vidět více logů nastavte v `configuration.yaml` vyšší level pro tuto custom komponentu.

```yaml
logger:
  default: warning
  logs:
    custom_components.fve_control: debug
```



