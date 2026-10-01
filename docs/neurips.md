# Croissant metadata for a NeurIPS dataset submission

NeurIPS 2026 requires every submission that introduces a dataset to provide a Croissant file with the core fields
and a minimal set of Responsible AI (RAI) fields, one file per dataset
([hosting guidelines](https://neurips.cc/Conferences/2026/EvaluationsDatasetsHosting),
[FAQ](https://neurips.cc/Conferences/2026/EvaluationsDatasetsFAQ)). Hosting platforms fill in only the core fields.
CroissantMiner drafts the RAI fields from your paper and adds them to the platform's file. The rules can change from
year to year, so check the current guidelines.

## What CroissantMiner fills

| Minimal RAI item (NeurIPS 2026) | Property | Filled by CroissantMiner |
|---|---|---|
| Data limitations | `rai:dataLimitations` | yes |
| Data biases | `rai:dataBiases` | yes |
| Personal or sensitive information | `rai:personalSensitiveInformation` | yes |
| Data use cases | `rai:dataUseCases` | yes |
| Social impact | `rai:dataSocialImpact` | yes |
| Synthetic data | `rai:hasSyntheticData` | no, add it yourself |
| Source datasets | `prov:wasDerivedFrom` | no, add it yourself |
| Provenance activities | `prov:wasGeneratedBy` | no; its content (collection, preprocessing, annotation) is in `rai:dataCollection`, `rai:dataPreprocessingProtocol` and `rai:dataAnnotationProtocol`, which CroissantMiner fills |

It also fills the other 15 RAI fields of Croissant 1.1 when the paper reports them, for example the annotation
platform, the annotators and the maintenance plan. A field the paper does not report is left out.

## 1. Host the dataset

Put the data on a platform that generates Croissant files, such as Hugging Face, Kaggle, OpenML or Dataverse. Its
file lists the data files and their columns. On Hugging Face it is at
`https://huggingface.co/api/datasets/<org>/<name>/croissant` once the dataset viewer can read the data. If you host
the data yourself, the guidelines suggest tools that create this file from your data folder.

## 2. Install CroissantMiner

```bash
git clone https://github.com/berkearda/croissantminer
cd croissantminer
pip install -e ".[validate]"
export ANTHROPIC_API_KEY=...      # or put it in a .env file in the folder you run from
```

## 3. Extract the fields from your paper and merge them into the platform's file

```bash
croissantminer extract paper.pdf --merge-into <org>/<name> -o croissant.json --fields values.json
```

This reads the paper, drafts the fields, adds them to the platform's file and checks the result. The platform's own
values (name, URL, license, files and columns) are kept. For a dataset on another platform, download its Croissant
file and pass the path or the URL instead of `<org>/<name>`. A private or gated Hugging Face dataset needs
`HF_TOKEN`. Add `--method triage-critique` to get a supporting quote for most values in `values.json`, which makes
the next step faster; it scores a little lower in the paper than the default.

## 4. Check and complete the file

- **Read every `rai:` field against the paper.** The values are drafts written by a language model.
- **Add the three items CroissantMiner does not fill** (see the table) and any field the paper does not report. The
  hosting guidelines link to an online editor for the RAI fields, and the
  [Croissant RAI specification](https://docs.mlcommons.org/croissant/docs/croissant-rai-spec.html) describes each
  property.
- **Anonymous submission?** The FAQ asks that no identifying information leaks, including through the Croissant
  file. The platform's file names the account that uploaded the data, so use an anonymous account or project name.
  From an anonymous paper the model may also take "Anonymous authors" as the creator or the page header as the
  publisher: remove such values.

## 5. Validate and submit

```bash
croissantminer validate croissant.json
```

You can also use the online [Croissant checker](https://huggingface.co/spaces/JoaquinVanschoren/croissant-checker)
named in the guidelines. Then give the dataset URL and upload the file to OpenReview as the guidelines describe.

## Time, cost and privacy

The default method takes about 30 seconds and a few US cents per paper ([all methods](../README.md#which-method-to-choose)).
Your paper is sent to the model provider (Anthropic or OpenAI) under your API key and the provider's terms.
