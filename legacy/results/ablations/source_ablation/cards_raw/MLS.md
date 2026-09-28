---
annotations_creators:
- expert-generated
language_creators:
- crowdsourced
- expert-generated
language:
- de
- nl
- fr
- it
- es
- pt
- pl
- en
license:
- cc-by-4.0
multilinguality:
- multilingual
size_categories:
- 100K<n<1M
source_datasets:
- original
task_categories:
- automatic-speech-recognition
- text-to-speech
- text-to-audio
paperswithcode_id: multilingual-librispeech
pretty_name: MultiLingual LibriSpeech
dataset_info:
- config_name: dutch
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 199959986
    num_examples: 3095
  - name: test
    num_bytes: 199298575
    num_examples: 3075
  - name: train
    num_bytes: 23931679031
    num_examples: 374287
  - name: 9_hours
    num_bytes: 139884664.668
    num_examples: 2153
  - name: 1_hours
    num_bytes: 15462181
    num_examples: 234
  download_size: 24376256629
  dataset_size: 24486284437.668
- config_name: french
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 157923970.696
    num_examples: 2416
  - name: test
    num_bytes: 158352158.582
    num_examples: 2426
  - name: train
    num_bytes: 16984935842.04
    num_examples: 258213
  - name: 9_hours
    num_bytes: 142796680.609
    num_examples: 2167
  - name: 1_hours
    num_bytes: 15675831
    num_examples: 241
  download_size: 17381581776
  dataset_size: 17459684482.927002
- config_name: german
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 224293581.302
    num_examples: 3469
  - name: test
    num_bytes: 225756069.096
    num_examples: 3394
  - name: train
    num_bytes: 31050881388
    num_examples: 469942
  - name: 9_hours
    num_bytes: 142777983.118
    num_examples: 2194
  - name: 1_hours
    num_bytes: 15714704
    num_examples: 241
  download_size: 31526161821
  dataset_size: 31659423725.516
- config_name: italian
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 81607596.048
    num_examples: 1248
  - name: test
    num_bytes: 83216752.046
    num_examples: 1262
  - name: train
    num_bytes: 3896742625
    num_examples: 59623
  - name: 9_hours
    num_bytes: 141671904.428
    num_examples: 2173
  - name: 1_hours
    num_bytes: 15560398
    num_examples: 240
  download_size: 4200633596
  dataset_size: 4218799275.522
- config_name: polish
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 32746725
    num_examples: 512
  - name: test
    num_bytes: 33735044
    num_examples: 520
  - name: train
    num_bytes: 1638889846
    num_examples: 25043
  - name: 9_hours
    num_bytes: 142005461
    num_examples: 2173
  - name: 1_hours
    num_bytes: 15681216
    num_examples: 238
  download_size: 1855342312
  dataset_size: 1863058292
- config_name: portuguese
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 57533473
    num_examples: 826
  - name: test
    num_bytes: 59141979
    num_examples: 871
  - name: train
    num_bytes: 2518553713.946
    num_examples: 37533
  - name: 9_hours
    num_bytes: 141641902.42
    num_examples: 2116
  - name: 1_hours
    num_bytes: 15697139
    num_examples: 236
  download_size: 2780836500
  dataset_size: 2792568207.366
- config_name: spanish
  features:
  - name: audio
    dtype: audio
  - name: original_path
    dtype: string
  - name: begin_time
    dtype: float64
  - name: end_time
    dtype: float64
  - name: transcript
    dtype: string
  - name: audio_duration
    dtype: float64
  - name: speaker_id
    dtype: string
  - name: chapter_id
    dtype: string
  - name: file
    dtype: string
  - name: id
    dtype: string
  splits:
  - name: dev
    num_bytes: 157804903.144
    num_examples: 2408
  - name: test
    num_bytes: 158526899.32
    num_examples: 2385
  - name: train
    num_bytes: 14562584188
    num_examples: 220701
  - name: 9_hours
    num_bytes: 142473624.48
    num_examples: 2110
  - name: 1_hours
    num_bytes: 15702048
    num_examples: 233
  download_size: 14971394533
  dataset_size: 15037091662.944
configs:
- config_name: dutch
  data_files:
  - split: dev
    path: dutch/dev-*
  - split: test
    path: dutch/test-*
  - split: train
    path: dutch/train-*
  - split: 9_hours
    path: dutch/9_hours-*
  - split: 1_hours
    path: dutch/1_hours-*
- config_name: french
  data_files:
  - split: dev
    path: french/dev-*
  - split: test
    path: french/test-*
  - split: train
    path: french/train-*
  - split: 9_hours
    path: french/9_hours-*
  - split: 1_hours
    path: french/1_hours-*
- config_name: german
  data_files:
  - split: dev
    path: german/dev-*
  - split: test
    path: german/test-*
  - split: train
    path: german/train-*
  - split: 9_hours
    path: german/9_hours-*
  - split: 1_hours
    path: german/1_hours-*
- config_name: italian
  data_files:
  - split: dev
    path: italian/dev-*
  - split: test
    path: italian/test-*
  - split: train
    path: italian/train-*
  - split: 9_hours
    path: italian/9_hours-*
  - split: 1_hours
    path: italian/1_hours-*
- config_name: polish
  data_files:
  - split: dev
    path: polish/dev-*
  - split: test
    path: polish/test-*
  - split: train
    path: polish/train-*
  - split: 9_hours
    path: polish/9_hours-*
  - split: 1_hours
    path: polish/1_hours-*
- config_name: portuguese
  data_files:
  - split: dev
    path: portuguese/dev-*
  - split: test
    path: portuguese/test-*
  - split: train
    path: portuguese/train-*
  - split: 9_hours
    path: portuguese/9_hours-*
  - split: 1_hours
    path: portuguese/1_hours-*
- config_name: spanish
  data_files:
  - split: dev
    path: spanish/dev-*
  - split: test
    path: spanish/test-*
  - split: train
    path: spanish/train-*
  - split: 9_hours
    path: spanish/9_hours-*
  - split: 1_hours
    path: spanish/1_hours-*
---

# Dataset Card for MultiLingual LibriSpeech

## Table of Contents
- [Dataset Description](#dataset-description)
  - [Dataset Summary](#dataset-summary)
  - [Supported Tasks and Leaderboards](#supported-tasks-and-leaderboards)
  - [Languages](#languages)
  - [How to use](#how-to-use)
- [Dataset Structure](#dataset-structure)
  - [Data Instances](#data-instances)
  - [Data Fields](#data-fields)
  - [Data Splits](#data-splits)
- [Dataset Creation](#dataset-creation)
  - [Curation Rationale](#curation-rationale)
  - [Source Data](#source-data)
  - [Annotations](#annotations)
  - [Personal and Sensitive Information](#personal-and-sensitive-information)
- [Considerations for Using the Data](#considerations-for-using-the-data)
  - [Social Impact of Dataset](#social-impact-of-dataset)
  - [Discussion of Biases](#discussion-of-biases)
  - [Other Known Limitations](#other-known-limitations)
- [Additional Information](#additional-information)
  - [Dataset Curators](#dataset-curators)
  - [Licensing Information](#licensing-information)
  - [Citation Information](#citation-information)
  - [Contributions](#contributions)

## Dataset Description

- **Homepage:** [MultiLingual LibriSpeech ASR corpus](http://www.openslr.org/94)
- **Repository:** [Needs More Information]
- **Paper:** [MLS: A Large-Scale Multilingual Dataset for Speech Research](https://arxiv.org/abs/2012.03411)
- **Leaderboard:** [🤗 Autoevaluate Leaderboard](https://huggingface.co/spaces/autoevaluate/leaderboards?dataset=facebook%2Fmultilingual_librispeech&only_verified=0&task=automatic-speech-recognition&config=-unspecified-&split=-unspecified-&metric=wer)

### Dataset Summary

This is a streamable version of the Multilingual LibriSpeech (MLS) dataset. 
The data archives were restructured from the original ones from [OpenSLR](http://www.openslr.org/94) to make it easier to stream.

MLS dataset is a large multilingual corpus suitable for speech research. The dataset is derived from read audiobooks from LibriVox and consists of 
8 languages - English, German, Dutch, Spanish, French, Italian, Portuguese, Polish. It includes about 44.5K hours of English and a total of about 6K hours for other languages.

### Supported Tasks and Leaderboards

- `automatic-speech-recognition`, `speaker-identification`: The dataset can be used to train a model for Automatic Speech Recognition (ASR). The model is presented with an audio file and asked to transcribe the audio file to written text. The most common evaluation metric is the word error rate (WER). The task has an active leaderboard which can be found at https://paperswithcode.com/dataset/multilingual-librispeech and ranks models based on their WER.
- `text-to-speech`, `text-to-audio`: The dataset can also be used to train a model for Text-To-Speech (TTS).

### Languages

The dataset is derived from read audiobooks from LibriVox and consists of 8 languages - English, German, Dutch, Spanish, French, Italian, Portuguese, Polish

### How to use

The `datasets` library allows you to load and pre-process your dataset in pure Python, at scale. The dataset can be downloaded and prepared in one call to your local drive by using the `load_dataset` function. 

For example, to download the German config, simply specify the corresponding language config name (i.e., "german" for German):
```python
from datasets import load_dataset
mls = load_dataset("facebook/multilingual_librispeech", "german", split="train")
```

Using the datasets library, you can also stream the dataset on-the-fly by adding a `streaming=True` argument to the `load_dataset` function call. Loading a dataset in streaming mode loads individual samples of the dataset at a time, rather than downloading the entire dataset to disk.
```python
from datasets import load_dataset
mls = load_dataset("facebook/multilingual_librispeech", "german", split="train", streaming=True)
print(next(iter(mls)))
```

*Bonus*: create a [PyTorch dataloader](https://huggingface.co/docs/datasets/use_with_pytorch) directly with your own datasets (local/streamed).

Local:

```python
from datasets import load_dataset
from torch.utils.data.sampler import BatchSampler, RandomSampler
mls = load_dataset("facebook/multilingual_librispeech", "german", split="train")
batch_sampler = BatchSampler(RandomSampler(mls), batch_size=32, drop_last=False)
dataloader = DataLoader(mls, batch_sampler=batch_sampler)
```

Streaming:

```python
from datasets import load_dataset
from torch.utils.data import DataLoader
mls = load_dataset("facebook/multilingual_librispeech", "german", split="train", streaming=True)
dataloader = DataLoader(mls, batch_size=32)
```

To find out more about loading and preparing audio datasets, head over to [hf.co/blog/audio-datasets](https://huggingface.co/blog/audio-datasets).

### Example scripts

Train your own CTC or Seq2Seq Automatic Speech Recognition models on MultiLingual Librispeech with `transformers` - [here](https://github.com/huggingface/transformers/tree/main/examples/pytorch/speech-recognition).

## Dataset Structure

### Data Instances

A typical data point comprises the path to the audio file, usually called `file` and its transcription, called `text`. Some additional information about the speaker and the passage which contains the transcription is provided.

```
{'file': '10900_6473_000030.flac',
 'audio': {'path': '10900_6473_000030.flac',
  'array': array([-1.52587891e-04,  6.10351562e-05,  0.00000000e+00, ...,
          4.27246094e-04,  5.49316406e-04,  4.57763672e-04]),
  'sampling_rate': 16000},
 'text': 'więc czego chcecie odemnie spytałem wysłuchawszy tego zadziwiającego opowiadania broń nas stary człowieku broń zakrzyknęli równocześnie obaj posłowie\n',
 'speaker_id': 10900,
 'chapter_id': 6473,
 'id': '10900_6473_000030'}
```


### Data Fields

- file: A filename .flac format.

- audio: A dictionary containing the audio filename, the decoded audio array, and the sampling rate. Note that when accessing the audio column: `dataset[0]["audio"]` the audio file is automatically decoded and resampled to `dataset.features["audio"].sampling_rate`. Decoding and resampling of a large number of audio files might take a significant amount of time. Thus it is important to first query the sample index before the `"audio"` column, *i.e.* `dataset[0]["audio"]` should **always** be preferred over `dataset["audio"][0]`.

- text: the transcription of the audio file.

- id: unique id of the data sample.

- speaker_id: unique id of the speaker. The same speaker id can be found for multiple data samples.
- chapter_id: id of the audiobook chapter which includes the transcription.

### Data Splits

|           Number of samples                  | Train | Train.9h | Train.1h  | Dev | Test |
| -----                       | ------ | ----- | ---- | ---- | ---- | 
| german | 469942 | 2194 | 241 | 3469 | 3394 |
| dutch | 374287 | 2153 | 234 | 3095 | 3075 |
| french | 258213 | 2167 | 241 | 2416 | 2426 |
| spanish | 220701 | 2110 | 233 | 2408 | 2385 |
| italian | 59623 | 2173 | 240 | 1248 | 1262 |
| portuguese | 37533 | 2116 | 236 | 826 | 871 |
| polish | 25043 | 2173 | 238 | 512 | 520 |

## Dataset Creation

### Curation Rationale

[Needs More Information]

### Source Data

#### Initial Data Collection and Normalization

[Needs More Information]

#### Who are the source language producers?

[Needs More Information]

### Annotations

#### Annotation process

[Needs More Information]

#### Who are the annotators?

[Needs More Information]

### Personal and Sensitive Information

The dataset consists of people who have donated their voice online. You agree to not attempt to determine the identity of speakers in this dataset.

## Considerations for Using the Data

### Social Impact of Dataset

[More Information Needed]

### Discussion of Biases

[More Information Needed]

### Other Known Limitations

[Needs More Information]

## Additional Information

### Dataset Curators

[Needs More Information]

### Licensing Information

Public Domain, Creative Commons Attribution 4.0 International Public License ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode))

### Citation Information

```
@article{Pratap2020MLSAL,
  title={MLS: A Large-Scale Multilingual Dataset for Speech Research},
  author={Vineel Pratap and Qiantong Xu and Anuroop Sriram and Gabriel Synnaeve and Ronan Collobert},
  journal={ArXiv},
  year={2020},
  volume={abs/2012.03411}
}
```


### Data Statistics

| Duration (h) | Train     | Dev   | Test  |
|--------------|-----------|-------|-------|
| English      | 44,659.74 | 15.75 | 15.55 |
| German       | 1,966.51  | 14.28 | 14.29 |
| Dutch        | 1,554.24  | 12.76 | 12.76 |
| French       | 1,076.58  | 10.07 | 10.07 |
| Spanish      | 917.68    | 9.99  | 10    |
| Italian      | 247.38    | 5.18  | 5.27  |
| Portuguese   | 160.96    | 3.64  | 3.74  |
| Polish       | 103.65    | 2.08  | 2.14  |

| # Speakers | Train |      | Dev |    | Test |    |
|------------|-------|------|-----|----|------|----|
|       Gender   | M     | F    | M   | F  | M    | F  |
| English    | 2742  | 2748 | 21  | 21 | 21   | 21 |
| German     | 81    | 95   | 15  | 15 | 15   | 15 |
| Dutch      | 9     | 31   | 3   | 3  | 3    | 3  |
| French     | 62    | 80   | 9   | 9  | 9    | 9  |
| Spanish    | 36    | 50   | 10  | 10 | 10   | 10 |
| Italian    | 22    | 43   | 5   | 5  | 5    | 5  |
| Portuguese | 26    | 16   | 5   | 5  | 5    | 5  |
| Polish     | 6     | 5    | 2   | 2  | 2    | 2  |

| # Hours / Gender | Dev  |      | Test |      |
|------------------|------|------|------|------|
|       Gender   | M    | F    | M    | F    |
| English          | 7.76 | 7.99 | 7.62 | 7.93 |
| German           | 7.06 | 7.22 | 7    | 7.29 |
| Dutch            | 6.44 | 6.32 | 6.72 | 6.04 |
| French           | 5.13 | 4.94 | 5.04 | 5.02 |
| Spanish          | 4.91 | 5.08 | 4.78 | 5.23 |
| Italian          | 2.5  | 2.68 | 2.38 | 2.9  |
| Portuguese       | 1.84 | 1.81 | 1.83 | 1.9  |
| Polish           | 1.12 | 0.95 | 1.09 | 1.05 |




### Contributions

Thanks to [@patrickvonplaten](https://github.com/patrickvonplaten) and [@polinaeterna](https://github.com/polinaeterna) for adding this dataset.