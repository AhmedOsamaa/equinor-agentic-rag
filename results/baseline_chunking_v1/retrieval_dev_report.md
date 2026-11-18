# Retrieval eval, dev (PILOT)

git `cc37ee1`, 2026-11-16T15:15:23+00:00, k=10. Mean [95% bootstrap CI]; n is the number of questions in the tier. Never blend the tiers.

## round_1 (n = 19)

| mode | hit@5 | hit@10 | coverage@10 | mrr@10 | ndcg@10 |
|---|---|---|---|---|---|
| vector | 0.84 [0.68, 1.00] | 0.84 [0.68, 1.00] | 0.84 [0.68, 1.00] | 0.67 [0.48, 0.84] | 0.68 [0.50, 0.86] |
| hybrid | 0.89 [0.74, 1.00] | 0.95 [0.84, 1.00] | 0.95 [0.84, 1.00] | 0.75 [0.59, 0.89] | 0.79 [0.64, 0.94] |
| hybrid_rerank | 0.84 [0.68, 1.00] | 0.89 [0.74, 1.00] | 0.89 [0.74, 1.00] | 0.72 [0.54, 0.89] | 0.76 [0.59, 0.92] |

Paired differences (a - b):

- hybrid - vector | hit@10: +0.105 [+0.000, +0.263], no supported difference
- hybrid - vector | mrr@10: +0.079 [-0.022, +0.182], no supported difference
- hybrid - vector | ndcg@10: +0.115 [+0.042, +0.191], interval excludes 0
- hybrid_rerank - hybrid | hit@10: -0.053 [-0.158, +0.000], no supported difference
- hybrid_rerank - hybrid | mrr@10: -0.026 [-0.198, +0.154], no supported difference
- hybrid_rerank - hybrid | ndcg@10: -0.033 [-0.160, +0.103], no supported difference

## round_2 (n = 19)

| mode | hit@5 | hit@10 | coverage@10 | mrr@10 | ndcg@10 |
|---|---|---|---|---|---|
| vector | 0.53 [0.32, 0.74] | 0.68 [0.47, 0.89] | 0.55 [0.37, 0.74] | 0.39 [0.22, 0.57] | 0.42 [0.25, 0.59] |
| hybrid | 0.58 [0.37, 0.79] | 0.63 [0.42, 0.84] | 0.55 [0.34, 0.76] | 0.36 [0.20, 0.54] | 0.41 [0.25, 0.58] |
| hybrid_rerank | 0.63 [0.42, 0.84] | 0.68 [0.47, 0.89] | 0.58 [0.37, 0.76] | 0.46 [0.27, 0.66] | 0.45 [0.29, 0.61] |

Paired differences (a - b):

- hybrid - vector | hit@10: -0.053 [-0.211, +0.105], no supported difference
- hybrid - vector | mrr@10: -0.022 [-0.152, +0.067], no supported difference
- hybrid - vector | ndcg@10: -0.004 [-0.106, +0.089], no supported difference
- hybrid_rerank - hybrid | hit@10: +0.053 [+0.000, +0.158], no supported difference
- hybrid_rerank - hybrid | mrr@10: +0.101 [-0.020, +0.238], no supported difference
- hybrid_rerank - hybrid | ndcg@10: +0.039 [-0.050, +0.141], no supported difference

## round_3 (n = 14)

| mode | hit@5 | hit@10 | coverage@10 | mrr@10 | ndcg@10 |
|---|---|---|---|---|---|
| vector | 0.86 [0.64, 1.00] | 0.86 [0.64, 1.00] | 0.82 [0.61, 1.00] | 0.65 [0.45, 0.85] | 0.67 [0.47, 0.86] |
| hybrid | 0.86 [0.64, 1.00] | 0.86 [0.64, 1.00] | 0.79 [0.57, 0.96] | 0.79 [0.57, 0.96] | 0.72 [0.53, 0.90] |
| hybrid_rerank | 0.93 [0.79, 1.00] | 0.93 [0.79, 1.00] | 0.86 [0.68, 1.00] | 0.80 [0.61, 0.96] | 0.76 [0.58, 0.94] |

Paired differences (a - b):

- hybrid - vector | hit@10: +0.000 [+0.000, +0.000], no supported difference
- hybrid - vector | mrr@10: +0.137 [+0.000, +0.292], no supported difference
- hybrid - vector | ndcg@10: +0.051 [-0.013, +0.121], no supported difference
- hybrid_rerank - hybrid | hit@10: +0.071 [+0.000, +0.214], no supported difference
- hybrid_rerank - hybrid | mrr@10: +0.014 [-0.129, +0.157], no supported difference
- hybrid_rerank - hybrid | ndcg@10: +0.044 [-0.032, +0.121], no supported difference

Mean latency per query (s, warm): vector 0.019, hybrid 0.021, hybrid_rerank 5.634

# Misses: 14 of 52 questions have no quote chunk in the top 10 for at least one mode

## havtil_co2-003 (round 1, type numerical, format text)

**Question:** Under Section 10 of the CO2 safety regulations, which section of Chapter IX of the Management Regulations is exempted from applying?

**Gold evidence:**
- havtil_co2 p7: "in Chapter IX of the Management Regulations with the exception of Section 34 apply correspondingly to the scope of these regulations."


**vector: MISS**

1. gain 0, havtil_management p20, `CHAPTER IX Reporting and information relating to offshore petroleum activities > Section 43`: # Section 43 # Supervision, decisions, enforcement etc. Chapter IX of the Framework Regulations applies correspondingly to these regulations. # Section 44 # Entry into force These regulations will enter into force on 1 January 2011. At this time, the Regulations relating to management in the petrole...
2. gain 0, havtil_framework p26, `CHAPTER IX Closing provisions > Section 72 Sanctions`: # Section 72 Sanctions Provisions with regard to penalties and other sanctions contained in the health, safety and environment legislation apply to violation of requirements stipulated in and pursuant to these regulations. # Section 73 # Entry into force The Regulations will enter into force on 1 Ja...
3. gain 0, havtil_co2 p5, `CHAPTER I Introductory provisions > Section 3`: # Section 3 # Relation to other legislation The regulations are based on the principles that are used in the HSE regulations for the petroleum activities, adapted to the risk conditions that transport and injection of CO2 represent. The regulations are limited to safety and working environment. The ...

- hybrid: quote chunk at rank 7
- hybrid_rerank: quote chunk at rank 1
## irena_rpgc2024-003 (round 1, type numerical, format table)

**Question:** In IRENA's 2024 assessment of renewable energy benefits, by how much did Germany's avoided fossil fuel expenditures exceed its avoided air pollution damage costs?

**Gold evidence:**
- irena_rpgc2024 p25: "|Avoided fossil fuel costs (USD billion)|179.8|16.4|28.3|5.0|"
- irena_rpgc2024 p25: "|Avoided air pollution damages (USD billion)|261.1|6.0|3.9|1.9|"

- vector: quote chunk at rank 1
- hybrid: quote chunk at rank 2

**hybrid_rerank: MISS**

1. gain 0, irena_rpgc2024 p3, `FOREWORD`: # FOREWORD ## Francesco La Camera _Director-General_ International Renewable Energy Agency The global energy system is undergoing a profound transformation, with renewables accounting for an increasing share of power generation. Global renewable power capacity additions in 2024 reached 582 GW – a 19...
2. gain 0, irena_rpgc2024 p36, `Beyond costs: Renewable energy benefits in terms of avoided fossil fuel use`: > _While this provides a useful benchmark for gauging the benefits of renewables, the model does not constitute a full cost-benefit analysis. It does not account for the costs incurred by renewable deployment (such as investment or integration costs), nor does it include indirect or induced effects ...
3. gain 0, irena_rpgc2024 p36, `Beyond costs: Renewable energy benefits in terms of avoided fossil fuel use`: In addition, renewables also reduce the need for fossil fuel infrastructure, such as fuel pipelines, storage terminals and thermal backup. Renewables do, however, increase the need for infrastructure throughout the renewable supply chain, as well as grid, storage and related infrastructure. Hybrid s...

## irena_rpgc2024-009 (round 1, type comparative, format table)

**Question:** Between 2010 and 2024, which generation source experienced a steeper percentage decrease in its levelised cost of electricity: utility-scale solar PV or onshore wind?

**Gold evidence:**
- irena_rpgc2024 p15: "|Solar PV|5283|691|-87%|15|17|13%|0.417|0.043|-90%|"
- irena_rpgc2024 p15: "|Onshore wind|2324|1041|-55%|27|34|26%|0.113|0.034|-70%|"


**vector: MISS**

1. gain 0, irena_rpgc2024 p19, `Future cost declines will slow but remain significant in high-growth regions`: # Future cost declines will slow but remain significant in high-growth regions Looking ahead, total installed costs are projected to decline further – although at a slower pace – as learning rates and economies of scale continue to drive efficiency gains. Globally, solar PV is expected to fall below...
2. gain 0, irena_rpgc2024 p85, `Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024`: # Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024 # HIGHLIGHTS - Between 2010 and 2024, the global weighted average LCOE of utility-scale solar PV plants declined by 90%, from USD 0.417/kWh to USD 0.043/kWh. The 2024 value, however, remained almost flat in comparison to ...
3. gain 0, irena_rpgc2024 p14, `EXECUTIVE SUMMARY`: # EXECUTIVE SUMMARY ## HIGHLIGHTS - On a levelised cost of electricity (LCOE) basis, renewables remained the most cost-competitive option for new electricity generation in 2024, with 91% of newly commissioned utility-scale capacity delivering power at a lower cost than the cheapest, newly installed ...


**hybrid: MISS**

1. gain 0, irena_rpgc2024 p28, `Renewables maintain cost leadership in global power markets`: # Renewables maintain cost leadership in global power markets Renewable energy technologies have experienced spectacular cost declines since 2010. This has been driven by improvements in technology, competitive supply chains and economies of scale (Figure 1.2). In 2010, the global weighted-average l...
2. gain 0, irena_rpgc2024 p14, `EXECUTIVE SUMMARY`: # EXECUTIVE SUMMARY ## HIGHLIGHTS - On a levelised cost of electricity (LCOE) basis, renewables remained the most cost-competitive option for new electricity generation in 2024, with 91% of newly commissioned utility-scale capacity delivering power at a lower cost than the cheapest, newly installed ...
3. gain 0, irena_rpgc2024 p85, `Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024`: # Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024 # HIGHLIGHTS - Between 2010 and 2024, the global weighted average LCOE of utility-scale solar PV plants declined by 90%, from USD 0.417/kWh to USD 0.043/kWh. The 2024 value, however, remained almost flat in comparison to ...


**hybrid_rerank: MISS**

1. gain 0, irena_rpgc2024 p14, `EXECUTIVE SUMMARY`: # EXECUTIVE SUMMARY ## HIGHLIGHTS - On a levelised cost of electricity (LCOE) basis, renewables remained the most cost-competitive option for new electricity generation in 2024, with 91% of newly commissioned utility-scale capacity delivering power at a lower cost than the cheapest, newly installed ...
2. gain 0, irena_rpgc2024 p28, `Renewables maintain cost leadership in global power markets`: # Renewables maintain cost leadership in global power markets Renewable energy technologies have experienced spectacular cost declines since 2010. This has been driven by improvements in technology, competitive supply chains and economies of scale (Figure 1.2). In 2010, the global weighted-average l...
3. gain 0, irena_rpgc2024 p3, `FOREWORD`: # FOREWORD ## Francesco La Camera _Director-General_ International Renewable Energy Agency The global energy system is undergoing a profound transformation, with renewables accounting for an increasing share of power generation. Global renewable power capacity additions in 2024 reached 582 GW – a 19...

## irena_rpgc2024-015 (round 1, type relationship, format text)

**Question:** How do greater distances from shore and deeper water depths influence the logistical and engineering requirements of offshore wind projects?

**Gold evidence:**
- irena_rpgc2024 p111: "Greater distances extend transit times for installing turbines and foundations, while deeper waters require more complex foundations, depending on site conditions."


**vector: MISS**

1. gain 0, irena_rpgc2024 p113, `Figure 4.3 Distance from shore and water depth for offshore wind projects by country, 2010–2024`: # Figure 4.3 Distance from shore and water depth for offshore wind projects by country, 2010–2024 Source: (Wood Mackenzie, 2025j). Notes: km = kilometre; m = metre; MW = megawatt. Water depth and distance from shore are determined by a range of site-specific factors. These characteristics are influe...
2. gain 0, irena_rpgc2024 p112, `TECHNOLOGICAL TRENDS`: Figure 4.2 presents trends in distance-to-port and water depth between 2010 and 2024 in Europe and the rest of the world. The trend towards deeper waters and sites farther from shore is most pronounced in Europe – the most mature market for offshore wind. Projects in this region are typically locate...
3. gain 0, irena_rpgc2024 p112, `TECHNOLOGICAL TRENDS`: Figure 4.3 highlights at the country level the varying trends in water depth and distance from shore for China, Belgium, the Netherlands, Germany, Denmark and the United Kingdom. In addition, the bubble sizes indicate increasing project capacities over time. This illustrates a noticeable shift towar...

- hybrid: quote chunk at rank 5
- hybrid_rerank: quote chunk at rank 1
## equinor_ar2025-102 (round 2, type numerical, format table)

**Question:** By what dollar margin did upstream capital additions outside Norway exceed those allocated to fields on the Norwegian continental shelf during 2025?

**Gold evidence:**
- equinor_ar2025 p195: "|Additions to PP&E, intangibles and equityaccounted investments|7,366| 8,224|"


**vector: MISS**

1. gain 0, equinor_ar2025 p58, `Financial performance > Group > Adjusted operating income*`: ### Adjusted operating income* 1) Including Other segment, please refer to Condensed financial statement in section 2.2 Financial performance for details. # 2.47 Adjusted Adjusted earnings per earnings per share* 2025 share* 2024 # 3.24 # E&P Norway E&P Norway revenues remained strong for 2025 with ...
2. gain 0, equinor_ar2025 p19, `EPN at a glance`: # EPN at a glance Exploration & Production Norway (EPN) is the backbone of our portfolio. Accounting for around two-thirds of equity production, EPN plays a vital role in Europe’s energy security, providing consistent, stable and high-value production with low emissions. With a legacy spanning more ...
3. gain 0, equinor_ar2025 p58, `Financial performance`: # Financial performance ## Group Higher gas prices and increased production of natural gas contributed to revenue growth in 2025 compared to 2024, despite lower liquids prices and stable liquids production. Results in the Marketing, Midstream and Processing segment were driven by Gas and Power, prim...


**hybrid: MISS**

1. gain 0, equinor_ar2025 p19, `EPN at a glance`: # EPN at a glance Exploration & Production Norway (EPN) is the backbone of our portfolio. Accounting for around two-thirds of equity production, EPN plays a vital role in Europe’s energy security, providing consistent, stable and high-value production with low emissions. With a legacy spanning more ...
2. gain 0, equinor_ar2025 p74, `Continued leadership in upstream carbon efficiency`: # Continued leadership in upstream carbon efficiency In 2025 absolute scope 1+2 operated greenhouse gas emissions were the same as in 2024, with a total of 10.1 million tonnes CO2e. This equates to a 34% reduction from our 2015 baseline13 , progressing toward our 2030 ambition of a 50% net reduction...
3. gain 0, equinor_ar2025 p219, `Net impairments/(reversal of impairments) > Exploration & Production Norway`: ## Exploration & Production Norway In 2023, the impairment mainly related to reduced expected reserves on a producing asset on the Norwegian Continental Shelf. ## Exploration & Production USA - offshore In 2025, the impairments related to producing assets in the Gulf of America following reduced pro...


**hybrid_rerank: MISS**

1. gain 0, equinor_ar2025 p55, `Portfolio composition`: # Portfolio composition For 2026 and 2027, we will continue to allocate capital to further develop and maximise value from the Norwegian continental shelf (NCS). At the same time, we will continue working on delivering focused growth in our international oil and gas portfolio and building our integr...
2. gain 0, equinor_ar2025 p74, `Continued leadership in upstream carbon efficiency`: # Continued leadership in upstream carbon efficiency In 2025 absolute scope 1+2 operated greenhouse gas emissions were the same as in 2024, with a total of 10.1 million tonnes CO2e. This equates to a 34% reduction from our 2015 baseline13 , progressing toward our 2030 ambition of a 50% net reduction...
3. gain 0, equinor_ar2025 p19, `EPN at a glance`: # EPN at a glance Exploration & Production Norway (EPN) is the backbone of our portfolio. Accounting for around two-thirds of equity production, EPN plays a vital role in Europe’s energy security, providing consistent, stable and high-value production with low emissions. With a legacy spanning more ...

## equinor_ar2025-111 (round 2, type comparative, format table)

**Question:** How did capital investment allocations for international extraction assets evolve between 2024 and 2025 in segmented reporting?

**Gold evidence:**
- equinor_ar2025 p195: "|Additions to PP&E, intangibles and equityaccounted investments|7,366| 8,224|"
- equinor_ar2025 p196: "|Additions to PP&E, intangibles and equity accounted investments|6,285|3,191|"


**vector: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, equinor_ar2025 p67, `Debt and liquidity management > Liquidity management > Investment type of liquid assets`: ### Investment type of liquid assets 2.0% 13.0% 14.0% 56.0% 15.0% Time deposits Corporate bonds Treasury bills and commercial papers Money market funds Current accounts ### Maturity profile of bonds issued USD billion USD EUR GBP NOK 8 7 6 5 4 3 2 1 0 2026-2028 2029-2031 2031-2040 2041-2050 # Balanc...
2. gain 1, equinor_ar2025 p195, `Note 5. Segments > Accounting policies`: Segment information for the years ended 31 December 2025, 2024, and 2023 are presented below. For revenues per geographical area, please see note 7 Total revenues and other income. For further information on the following items affecting the segments, please refer to the related notes: note 6 Acquis...
3. gain 0, equinor_ar2025 p247, `At 31 December 2024`: 1) Previously reported number for 2024 has been restated due to a change in classification of cash collaterals for commodity derivative transactions. Reference is made to note 2 Accounting Policies for more information.


**hybrid: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, equinor_ar2025 p55, `Investments`: # Investments In 2025, organic capital expenditures amounted to USD 13.1 billion. The organic capital expenditures* in 2024 and in 2023 were USD 12.1 billion and USD 10.2 billion, respectively. T he organic capital expenditures* increased compared to 2024 mainly due to investments in a US offshore w...
2. gain 0, equinor_ar2025 p60, `E&P International`: # E&P International Total revenues and other income, as well as net operating income, decreased in 2025 compared to 2024. This decrease is mainly due to lower volumes and a decline in liquid commodity prices in 2025, together with the gain on the sale of the Nigerian business in 2024. These factors ...
3. gain 0, irena_rpgc2024 p41, `Figure 1.12 LCOE breakdown in selected regions, 2024`: In 2023, IRENA published a robust methodology combining expert elicitation, semi-structured interviews and a benchmark modelling tool to estimate the WACC for solar PV, onshore wind and offshore wind across major global markets (IRENA, 2023a). The benchmark tool accounts for macroeconomic factors, s...


**hybrid_rerank: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, equinor_ar2025 p60, `E&P International`: # E&P International Total revenues and other income, as well as net operating income, decreased in 2025 compared to 2024. This decrease is mainly due to lower volumes and a decline in liquid commodity prices in 2025, together with the gain on the sale of the Nigerian business in 2024. These factors ...
2. gain 0, equinor_ar2025 p55, `Investments`: # Investments In 2025, organic capital expenditures amounted to USD 13.1 billion. The organic capital expenditures* in 2024 and in 2023 were USD 12.1 billion and USD 10.2 billion, respectively. T he organic capital expenditures* increased compared to 2024 mainly due to investments in a US offshore w...
3. gain 0, equinor_ar2025 p181, `Consolidated statement of cash flows`: # Consolidated statement of cash flows |||Fullyear|||||Fullyear|| |---|---|---|---|---|---|---|---|---| |(Increase)/decrease in financial investments2)|1,571|9,364|443|s ne em ncues e na acquson o per cen o e s as an additional investment of USD 0.9 billion in 2025 . See note 16 Fin|res n rse ancial...

## equinor_ar2025-116 (round 2, type spanning, format table)

**Question:** How do capital investments dedicated to the renewable energy branch in segment reporting compare in dollar magnitude to expenditures verified as aligned with European Union sustainable taxonomy criteria?

**Gold evidence:**
- equinor_ar2025 p118: "|Total CapEx KPI|||16.1%|2,118|14.7%|14.7%|"
- equinor_ar2025 p195: "|Additions to PP&E, intangibles and equityaccounted investments|7,366| 8,224|1,199|1,142|2,837|124|"


**vector: MISS**

1. gain 0, irena_rpgc2024 p23, `Cost of capital remains a key barrier in high-risk markets`: # Cost of capital remains a key barrier in high-risk markets Renewable energy projects are capital-intensive, with most costs incurred up front and recovered over long operating lifetimes. As a result, the LCOE is highly sensitive to financing conditions. In 2024, financing costs9 represented an imp...
2. gain 0, irena_rpgc2024 p197, `ANNEX I COST METRIC METHODOLOGY`: One of the key advantages of using a weighted average is that it accounts for the scale of individual projects, ensuring that the larger ones have a proportionate influence on the final result. This method prevents distortion caused by smaller or outlier projects with unusually high costs. It thus p...
3. gain 0, irena_rpgc2024 p198, `ANNEX I COST METRIC METHODOLOGY`: The LCOE of renewable energy technologies varies by technology, country and project, based on the renewable energy resource, capital and operating costs, and the efficiency/performance of the technology. The approach used in the analysis presented here is based on a discounted cash flow (DCF) techni...


**hybrid: MISS**

1. gain 0, equinor_ar2025 p116, `EU Taxonomy for sustainable activities`: Equinor's EU Taxonomy alignment is primarily attributable to its Empire Wind project in the US (economic activity: electricity generation from wind power), which is expected to start production in late 2026. Equinor’s other wind power projects contribute insignificantly to the Taxonomy KPIs and, as ...
2. gain 0, equinor_ar2025 p311, `c) Organic capital expenditures`: # c) Organic capital expenditures Capital expenditures is defined as Additions to PP&E, intangibles and equity accounted investments, which excludes assets held for sale, as presented in note 5 Segments to the consolidated financial statements. Organic capital expenditures are capital expenditures e...
3. gain 0, equinor_ar2025 p55, `Investments`: # Investments In 2025, organic capital expenditures amounted to USD 13.1 billion. The organic capital expenditures* in 2024 and in 2023 were USD 12.1 billion and USD 10.2 billion, respectively. T he organic capital expenditures* increased compared to 2024 mainly due to investments in a US offshore w...


**hybrid_rerank: MISS**

1. gain 0, irena_rpgc2024 p12, `ABBREVIATIONS`: AC alternating current kWh kilowatt hour AGS advanced geothermal system LACE levelised avoided cost of electricity AI artificial intelligence LCOE levelised cost of electricity AU African Union LCOS levelised cost of storage BECCS bioenergy with carbon capture and storage LDES long duration energy s...
2. gain 0, equinor_ar2025 p95, `Interests and views of stakeholders`: |Stakeholders|How engagement is organised|Purpose of engagements|Outcomes of engagements| |---|---|---|---| |Suppliers|• Annual management meeting with key suppliers • Risk-based on-site supplier assessments as part of ongoing human rights due diligence • Formal meetings with suppliers • Supplier sc...
3. gain 0, equinor_ar2025 p55, `Investments`: # Investments In 2025, organic capital expenditures amounted to USD 13.1 billion. The organic capital expenditures* in 2024 and in 2023 were USD 12.1 billion and USD 10.2 billion, respectively. T he organic capital expenditures* increased compared to 2024 mainly due to investments in a US offshore w...

## equinor_ar2025-117 (round 2, type spanning, format text)

**Question:** What ownership structure was created through the year-end merger of upstream assets in the United Kingdom, and what initial carrying value was assigned to that holding as an equity-accounted asset?

**Gold evidence:**
- equinor_ar2025 p40: "The E&P International segment divested its offshore UK assets and received a 50% ownership interest in Adura, a joint venture with Shell."
- equinor_ar2025 p222: "|of which investment in Adura|5,574|"


**vector: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, equinor_ar2025 p244, `Note 27. Related parties`: # Note 27. Related parties ## Transactions with the Norwegian state The Norwegian state is the majority shareholder of Equinor and also holds major investments in other Norwegian companies. As of 31 December 2025, the Norwegian state had an ownership interest in Equinor of 67.0% (excluding Folketryg...
2. gain 0, equinor_ar2025 p198, `Note 6. Acquisitions and disposals > Accounting policies > Business combinations and divestments`: ### Business combinations and divestments Business combinations, except for transactions between entities under common control, are accounted for using the acquisition method when control is transferred to the Group. The acquired identifiable assets, liabilities and contingent liabilities are measur...
3. gain 0, equinor_ar2025 p266, `Note 10. Investments in subsidiaries and other equity accounted companies > The following table shows significant subsidiaries held by Equinor ASA at 31 December 2025:`: ## The following table shows significant subsidiaries held by Equinor ASA at 31 December 2025: |Name|Ownership share in %|Country of incorporation| |---|---|---| |Equinor Angola Block 17 AS|100|Norway| |Equinor Energy AS|100|Norway| |Equinor Insurance AS|100|Norway| |Equinor Low Carbon Solutions AS|...


**hybrid: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, equinor_ar2025 p266, `Note 10. Investments in subsidiaries and other equity accounted companies > The following table shows significant subsidiaries held by Equinor ASA at 31 December 2025:`: ## The following table shows significant subsidiaries held by Equinor ASA at 31 December 2025: |Name|Ownership share in %|Country of incorporation| |---|---|---| |Equinor Angola Block 17 AS|100|Norway| |Equinor Energy AS|100|Norway| |Equinor Insurance AS|100|Norway| |Equinor Low Carbon Solutions AS|...
2. gain 1, equinor_ar2025 p222, `Joint ventures and other equity accounted investments`: 1) For 2024 this is mainly related to swap of US Offshore Wind assets, see also note 6 Acquisitions and disposals. Equity accounted investments consist of several investments, Adura is considered to be significant on individual basis. None of the other investments are above USD 0.9 billion and none ...
3. gain 0, equinor_ar2025 p244, `Note 27. Related parties`: # Note 27. Related parties ## Transactions with the Norwegian state The Norwegian state is the majority shareholder of Equinor and also holds major investments in other Norwegian companies. As of 31 December 2025, the Norwegian state had an ownership interest in Equinor of 67.0% (excluding Folketryg...


**hybrid_rerank: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, equinor_ar2025 p216, `Note 14. Impairments`: # Note 14. Impairments Accounting policies Impairment of property, plant and equipment, right-of-use assets, intangible assets including goodwill and equity accounted investments Equinor assesses individual assets or groups of assets for impairment when events or changes in circumstances indicate th...
2. gain 1, equinor_ar2025 p222, `Joint ventures and other equity accounted investments`: 1) For 2024 this is mainly related to swap of US Offshore Wind assets, see also note 6 Acquisitions and disposals. Equity accounted investments consist of several investments, Adura is considered to be significant on individual basis. None of the other investments are above USD 0.9 billion and none ...
3. gain 0, equinor_ar2025 p258, `Note 2. Financial risk management and measurement of financial instruments > Measurement of financial instruments by categories > Assets`: |(in USD million)|Note|Amortised cost|Fair value through profit or loss|Non- financial liabilities|Total carrying amount| |---|---|---|---|---|---| |At 31 December 2024|||||| |Liabilities|||||| |Non-current finance debt|16|19,224|||19,224| |Liabilities to subsidiaries and other equity accounted comp...

## havtil_co2-102 (round 2, type temporal, format text)

**Question:** Following what recurring year-end timetable was the offshore greenhouse gas containment framework revised across consecutive years after 2021?

**Gold evidence:**
- havtil_co2 p4: "Amended 19 December 2022."
- havtil_co2 p4: "Amended 18 December 2023."
- havtil_co2 p4: "Last amenden by the Norwegian Ocean Industry Authority 18 December 2024."

- vector: quote chunk at rank 7

**hybrid: MISS**

1. gain 0, irena_rpgc2024 p110, `INTRODUCTION`: # INTRODUCTION Offshore wind technology has matured rapidly since 2010, achieving significant progress in innovation, cost reduction and geographical diversification. At the end of 2024, total global offshore wind capacity was 82.9 GW37 (IRENA, 2025d), although new capacity additions were down 26%, ...
2. gain 0, equinor_ar2025 p115, `Methodologies greenhouse gas emissions`: - Category 4 – Upstream transportation and distribution: Emissions in this category comprise maritime transportation, including tankers and offshore vessels (such as supply, project, and seismic vessels), onshore transportation of goods and waste, and helicopter operations. Emissions are calculated ...
3. gain 0, irena_rpgc2024 p207, `CHANGING FINANCING CONDITIONS FOR RENEWABLES AND THE WACC`: The WACC values surveyed in 2021 were generally representative of financing conditions in 2020 and 2021. Given most onshore wind and solar PV projects are financed in the year prior to commissioning, the WACC values used for 2022 are unchanged from the benchmark values for 2021. However, with inflat...


**hybrid_rerank: MISS**

1. gain 0, irena_rpgc2024 p110, `INTRODUCTION`: # INTRODUCTION Offshore wind technology has matured rapidly since 2010, achieving significant progress in innovation, cost reduction and geographical diversification. At the end of 2024, total global offshore wind capacity was 82.9 GW37 (IRENA, 2025d), although new capacity additions were down 26%, ...
2. gain 0, equinor_ar2025 p105, `Ambitions related to climate change`: ||Ba|seline|202|5 Results|Ambiti|ons|| |---|---|---|---|---|---|---|---| ||Year|Value|2025|% vs. baseline|2030 2035|2040|2050| |Operated scope 1+2 GHG emissions1 (million tonnes CO2e)|2015|15.3|10.1|-34%|-45% (gross) -50% (net)||| |Upstream CO2 intensity2 (kg CO2/boe)|||6.3||6.0||| |Methane emission...
3. gain 0, equinor_ar2025 p100, `E1 - Climate change > Material impacts, risks and opportunities`: |Material impact, risk or opportunity|Category|Description|Our approach| |---|---|---|---| |Greenhouse gas emissions|Negative actual impact|Greenhouse gas (GHG) emissions contribute to global atmospheric CO2levels and climate change. Equinor has significant direct greenhouse gas emissions from our o...

## havtil_framework-104 (round 2, type spanning, format text)

**Question:** What formal framework governs technical audits when compliance checks are required, and what power do government inspectors possess to mandate such reviews?

**Gold evidence:**
- havtil_framework p12: "When verifications are deemed necessary, they shall be carried out according to a comprehensive and unambiguous verification programme and verification basis."
- havtil_framework p25: "the supervisory authorities can order the operator to carry out verifications itself, or to have such verifications performed by others"

- vector: quote chunk at rank 1

**hybrid: MISS**

1. gain 0, equinor_ar2025 p292, `Compliance and business integrity risks`: # Compliance and business integrity risks ## Supervisions, regulatory reviews and reporting _Supervision, review and sanctions for violations of laws and regulations at the supranational, national and local level may lead to legal liability, substantial fines, claims for damages, criminal sanctions ...
2. gain 0, equinor_ar2025 p166, `Prevention and detection of corruption and bribery`: We communicate our expectations in respect of our anti-bribery and anti-corruption compliance programme as part of communicating our expectations in respect of our Code of Conduct and through training, as set out in G1-1 and the ‘Training; section below. In addition Equinor’s expectations are commun...
3. gain 0, equinor_ar2025 p167, `Internal investigations and reporting`: executive committee and BAC. The SSEC reviews the results of significant audits and investigations within the areas of safety, security, sustainability and ethics on a regular basis. # Metrics and Targets We aim to continuously monitor and evaluate the effectiveness of our compliance program as part...

- hybrid_rerank: quote chunk at rank 5
## irena_rpgc2024-105 (round 2, type temporal, format text)

**Question:** How did heat retention operational capacity change across sunlight-concentrating generating stations from 2010 to 2024, and when did this duration achieve its historical maximum?

**Gold evidence:**
- irena_rpgc2024 p135: "thermal storage capacity for solar thermal plants in the IRENA renewable costs database increased from 3.5 hours to 8.5 hours between 2010 and 2024,"
- irena_rpgc2024 p135: "reaching its highest capacity – 17.5 hours – in 2021, when the Cerro Dominador 110 MW ST project, located in Chile’s Atacama Desert, was commissioned."


**vector: MISS**

1. gain 0, irena_rpgc2024 p87, `HIGHLIGHTS`: Notes: kW = kilowatt; kWh = kilowatt hour; USD = United States dollar. # INTRODUCTION By the end of 2024, over 1859 GW of solar PV systems had been installed globally, with 452 GW of newlyinstalled systems being commissioned in 2024 alone (IRENA, 2025d). This was 26.7% more than in 2023. Solar PV al...
2. gain 0, irena_rpgc2024 p130, `INTRODUCTION`: Linear-focusing CSP plants using linear Fresnel collectors are less common. This type of plant relies on an array of almost flat mirrors placed at different angles that concentrate the sun’s rays onto an elevated linear receiver above the mirror array. Unlike parabolic trough systems, in Fresnel col...
3. gain 0, irena_rpgc2024 p31, `Key technical-economic indicators: Capacity factors, total installed costs and the LCOE`: # Key technical-economic indicators: Capacity factors, total installed costs and the LCOE Between 2022 and 2024, new geothermal power generators maintained the highest and most stable capacity factors of all renewable energy technology types. With weighted-average capacity factors of over 80%, this ...

- hybrid: quote chunk at rank 4
- hybrid_rerank: quote chunk at rank 5
## irena_rpgc2024-107 (round 2, type temporal, format table)

**Question:** How did the central operating productivity metric for ground-mounted solar electric projects transition through the benchmark milestones of 2010, 2018, and 2024?

**Gold evidence:**
- irena_rpgc2024 p99: "|2010|11.1% 15.0%|25.2%|"
- irena_rpgc2024 p99: "|2018|12.5% 17.9%|27.0%|"
- irena_rpgc2024 p99: "|2024|11.5% 17.4%|22.6%|"


**vector: MISS**

1. gain 0, irena_rpgc2024 p85, `Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024`: # Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024 # HIGHLIGHTS - Between 2010 and 2024, the global weighted average LCOE of utility-scale solar PV plants declined by 90%, from USD 0.417/kWh to USD 0.043/kWh. The 2024 value, however, remained almost flat in comparison to ...
2. gain 0, irena_rpgc2024 p61, `Short-term CAPEX projections, 2025–2029`: Recent independent projections foresee global LCOE declines of between 22% and 49% by 2035 across clean energy technologies. This includes a 31% drop for fixed-axis PV and 50% for battery storage systems (BNEF, 2025a). These trajectories are driven by reductions in TIC and supply capacity (particula...
3. gain 0, irena_rpgc2024 p42, `TECHNOLOGY SPOTLIGHT: SOLAR`: # TECHNOLOGY SPOTLIGHT: SOLAR ## Deployment leaders and global trends In 2024, utility-scale solar photovoltaics (PV) dominated global renewable capacity additions. Some 452 GW of this technology was added globally,21 representing 78% of total renewable additions. China remained the pre-eminent mark...


**hybrid: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, irena_rpgc2024 p106, `Box 3.3 Unpacking the decline in utility-scale solar PV LCOE from 2010 to 2024`: Note: See Annex III for regional country groupings. # Box 3.4 G20 solar PV trends, 2010–2024 In recent decades, the G20 group has been central to the scale-up of solar PV. Over the 2010–2024 period, G20 countries accounted for 92% of global cumulative solar PV installed capacity. In 2024, they were ...
2. gain 0, irena_rpgc2024 p85, `Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024`: # Figure 2.16 Onshore wind weighted average LCOE in smaller markets, 2010–2024 # HIGHLIGHTS - Between 2010 and 2024, the global weighted average LCOE of utility-scale solar PV plants declined by 90%, from USD 0.417/kWh to USD 0.043/kWh. The 2024 value, however, remained almost flat in comparison to ...
3. gain 0, irena_rpgc2024 p103, `LCOE`: # LCOE The global weighted average LCOE of utility-scale solar PV remained flat in 2024, registering a value of USD 0.043/kWh for projects commissioned that year. This value was 0.6% higher than in 2023 and 90% lower than in 2010. During 2024, the 5th and 95th percentile range for all the projects s...


**hybrid_rerank: MISS** (a right-page chunk without the quote is in the top 10: check for a split quote)

1. gain 0, irena_rpgc2024 p146, `TOTAL INSTALLED COSTS`: As indicated earlier, two upward trends in the global weighted average total installed costs for hydropower can be identified between 2010 and 2024. The first occurred from 2010 to 2017, followed by a notable decrease in 2018. A second period of rising costs then began after 2019 and continued throu...
2. gain 0, irena_rpgc2024 p150, `CAPACITY FACTORS`: Between 2010 and 2024, the annual global weighted average capacity factor of newly commissioned small hydropower projects increased from 48% to 52% (Figure 6.7). Excluding the years 2017, 2018 and 2022 – for which there is a lack of data – the annual 5th percentile of small hydropower projects range...
3. gain 0, irena_rpgc2024 p106, `Box 3.3 Unpacking the decline in utility-scale solar PV LCOE from 2010 to 2024`: Note: See Annex III for regional country groupings. # Box 3.4 G20 solar PV trends, 2010–2024 In recent decades, the G20 group has been central to the scale-up of solar PV. Over the 2010–2024 period, G20 countries accounted for 92% of global cumulative solar PV installed capacity. In 2024, they were ...

## cross-307 (round 3, type relationship, format text)

**Question:** Equinor is building the Empire Wind offshore wind farm off New York. What LCOE did IRENA report for offshore wind in the United States in 2024, and what did it say explains such a high level?

**Gold evidence:**
- equinor_ar2025 p8: "our New York offshore wind farm, Empire Wind"
- irena_rpgc2024 p46: "the United States recorded one of the highest LCOEs, at USD 0.123/kWh, reflecting elevated financing costs, supply chain constraints and delayed project timelines"


**vector: MISS**

1. gain 0, equinor_ar2025 p47, `Renewables pipeline`: # Renewables pipeline For Offshore renewables, Equinor is currently developing several offshore wind projects. - Empire Wind, owned 100% by Equinor, received the final investment decision (FID) and secured a project financing package of USD 3 billion in 2024. During 2025, the project progressed acco...
2. gain 0, equinor_ar2025 p63, `REN > US Offshore Wind`: ## US Offshore Wind There is an increased risk associated with offshore wind projects in the US, including the development of the Empire Wind project. The Bureau of Ocean Energy Management issued a second stop-work order on 22 December 2025 (the Order), ordering the suspension of ongoing activities ...
3. gain 0, equinor_ar2025 p219, `Net impairments/(reversal of impairments) > Marketing, Midstream & Processing`: ## Marketing, Midstream & Processing In 2025, the net impairment reversal mainly related to increased refinery margin assumptions combined with extended economic lifetime of the relevant asset. In 2023, the impairment mainly related to expectations of stabilizing refinery margins at a lower level th...


**hybrid: MISS**

1. gain 0, equinor_ar2025 p125, `Impact, risk and opportunity management > Net positive impact plans`: ## Net positive impact plans From 2023, Equinor operated projects that geographically overlap with a protected area or area of high biodiversity value, are required to develop a net positive impact plan (NPI) (see E4-5 Methodologies for details). In 2025 our first NPI plan was completed by Empire Wi...
2. gain 0, equinor_ar2025 p219, `Net impairments/(reversal of impairments) > Marketing, Midstream & Processing`: ## Marketing, Midstream & Processing In 2025, the net impairment reversal mainly related to increased refinery margin assumptions combined with extended economic lifetime of the relevant asset. In 2023, the impairment mainly related to expectations of stabilizing refinery margins at a lower level th...
3. gain 0, equinor_ar2025 p200, `Acquisitions > Swap of US Offshore Wind assets`: ## Swap of US Offshore Wind assets On 24 January 2024, Equinor entered into a swap agreement with bp to acquire bp’s 50% share and take full ownership of Empire Offshore Wind Holdings LLC, including the Empire Wind lease and projects (Empire Wind), in exchange for its 50% share in Beacon Wind Holdin...

- hybrid_rerank: quote chunk at rank 5
## cross-308 (round 3, type comparative, format table)

**Question:** Equinor's Dogger Bank offshore wind farm is in the UK. How did the UK's weighted average LCOE for offshore wind projects commissioned in 2024 compare with the European average?

**Gold evidence:**
- equinor_ar2025 p110: "Dogger Bank (UK), Empire Wind 1 (USA)"
- irena_rpgc2024 p126: "United Kingdom 0.218 0.228 0.237 0.057 0.059 0.063"
- irena_rpgc2024 p126: "Europe 0.142 0.208 0.246 0.056 0.080 0.125"


**vector: MISS**

1. gain 0, equinor_ar2025 p47, `Renewables pipeline`: # Renewables pipeline For Offshore renewables, Equinor is currently developing several offshore wind projects. - Empire Wind, owned 100% by Equinor, received the final investment decision (FID) and secured a project financing package of USD 3 billion in 2024. During 2025, the project progressed acco...
2. gain 0, irena_rpgc2024 p109, `HIGHLIGHTS36`: # HIGHLIGHTS36 - Between 2010 and 2024, the global weighted average LCOE of offshore wind declined by 62%, from USD 0.208/kWh to USD 0.079/kWh. In 2024, the global weighted average LCOE increased by 4%, year-on-year, after a record low of USD 0.076/kWh in 2023. This increase was driven in part by sh...
3. gain 0, irena_rpgc2024 p125, `LCOE`: # LCOE Between 2010 and 2024, the global weighted average LCOE of offshore wind fell by 62%, from USD 0.208/kWh to USD 0.079/kWh (Figure 4.12). While this reflects substantial long-term progress, the 2024 figure marks a slight increase (4%) compared to the record low of USD 0.076/kWh achieved in 202...


**hybrid: MISS**

1. gain 0, irena_rpgc2024 p125, `LCOE`: Notes: kWh = kilowatt; MW = megawatt; USD = United States dollar. Table 4.4 presents the regional and country weighted average LCOE of offshore wind farms in Europe and Asia. Overall, Asia had a slightly lower weighted average LCOE, at USD 0.078/kWh, compared to Europe’s USD 0.080/kWh. Within market...
2. gain 0, irena_rpgc2024 p125, `LCOE`: # LCOE Between 2010 and 2024, the global weighted average LCOE of offshore wind fell by 62%, from USD 0.208/kWh to USD 0.079/kWh (Figure 4.12). While this reflects substantial long-term progress, the 2024 figure marks a slight increase (4%) compared to the record low of USD 0.076/kWh achieved in 202...
3. gain 0, irena_rpgc2024 p109, `HIGHLIGHTS36`: # HIGHLIGHTS36 - Between 2010 and 2024, the global weighted average LCOE of offshore wind declined by 62%, from USD 0.208/kWh to USD 0.079/kWh. In 2024, the global weighted average LCOE increased by 4%, year-on-year, after a record low of USD 0.076/kWh in 2023. This increase was driven in part by sh...


**hybrid_rerank: MISS**

1. gain 0, irena_rpgc2024 p109, `HIGHLIGHTS36`: # HIGHLIGHTS36 - Between 2010 and 2024, the global weighted average LCOE of offshore wind declined by 62%, from USD 0.208/kWh to USD 0.079/kWh. In 2024, the global weighted average LCOE increased by 4%, year-on-year, after a record low of USD 0.076/kWh in 2023. This increase was driven in part by sh...
2. gain 0, irena_rpgc2024 p125, `LCOE`: # LCOE Between 2010 and 2024, the global weighted average LCOE of offshore wind fell by 62%, from USD 0.208/kWh to USD 0.079/kWh (Figure 4.12). While this reflects substantial long-term progress, the 2024 figure marks a slight increase (4%) compared to the record low of USD 0.076/kWh achieved in 202...
3. gain 0, irena_rpgc2024 p122, `CAPACITY FACTORS`: Between 2010 and 2024, the weighted average capacity factor for projects commissioned in Europe increased from 39% to 48%. In 2024, capacity factors in Europe ranged from 45% at the 5th percentile to 53% at the 95th percentile. In comparison, projects commissioned in China that year had a weighted a...
