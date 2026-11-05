# Current product scope

Product direction and implementation status, November 5, 2026.

## Who we are building for

Sequencing labs are the first target customers. They already produce genomic reports and need help assembling the treatment evidence behind a patient's findings. Hospitals without molecular tumor boards are the next segment. Initial clinical evaluation is planned in Nepal, where drug access and cost are part of the problem.

The aim is to put ranked drug evidence, its sources and its limitations in front of an oncologist. The clinician interprets the result and decides what to do. Supporting several cancer types fits this workflow; it does not mean the product offers every part of cancer care.

## Prototype and planned offering

| Area | Current state | Planned work |
|:--|:--|:--|
| Genomic input | File upload and VCF parsing exist | Reliable lab integration and report input handling |
| Evidence matching | OncoKB/static evidence lookup, CIViC integrations and a composite ranker exist | Review performance through the actual application workflow |
| Patient-wide ranking | The main candidate path uses the first targetable mutation; other sources can add candidates | Combine relevant alterations without outcome-based selection |
| Copy-number changes and fusions | Models and optional modules exist; the CHORD runner handles them separately | Verify ingestion, persistence and ranking together in the normal upload flow |
| Clinical context | Cancer/alteration gates and limited treatment-line rules exist | Collect and pass treatment-line information through the application |
| Local access and cost | No dedicated geographic availability or affordability layer | Add those data beside the evidence |
| Delivery | Public code and a frontend demo | Hosted workspace, support and validation at each site |
| Adoption | No paying customers or hospital deployments reported | Independent review, partner-site evaluation and paying pilots |

The proposed lab price is $25 per report. It is a commercial plan, not current revenue. The code is MIT licensed; evidence databases have their own access and licensing terms.

## What has been measured

The saved CHORD results cover 2,505 patients selected under the benchmark's drug-to-alteration map. The experiment uses received treatments to select input alterations and sorts evidence lookups rather than running the complete application ranker. The same target map filters CIViC candidates. Those results do not establish independent whole-profile or prospective clinical performance.

The application ranker, frozen holdout and curated regression gate are separate evaluation contexts. See [BENCHMARK.md](BENCHMARK.md) for their sources and limitations. Passing software tests does not establish clinical validity.

## Research modules

Discovery briefs, marketplace bidding and crowdfunding are separate experiments. They are outside the initial lab offering, proposed per-report price and CHORD benchmark. They do not establish a treatment pathway through custom manufacture. Multi-omics, federated learning and mobile applications have no committed delivery schedule.

The historical preprint covers that broader research agenda. Its published title and citation are preserved. Scientific corrections belong in the explicit reconciliation and publication process.
