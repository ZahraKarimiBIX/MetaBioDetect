# 🧬 MetaBioDetect Platform(GUI-Based)

This repository provides MetaBioDetect a **GUI platform for MetaBarcoding data analysis**, supporting workflows from raw reads to final analyzed outputs. It is designed for flexibility, allowing users to run the full pipeline or individual steps independently.
MetaBioDetect has been designed to be user-friendly and easily accessible across different operating systems, including macOS, Windows, and Linux. The platform can be downloaded by users from the GitHub repository. For Windows users, MetaBioDetect is also available as a compiled executable file, allowing the software to be run without requiring additional installation or configuration.
This guide provides detailed instructions on software installation, database management, workflow execution, parameter configuration, and interpretation of results. It serves as a comprehensive resource to help users effectively utilize the full range of features available in MetaBioDetect.
A User Manual is also provided, which contains the same information presented in this guide but with additional screenshots and practical examples. The images provide visual, step-by-step guidance to help users understand the software interface, follow the workflow, configure parameters, and interpret the results more easily.
---

##  Download and installation
MetaBioDetect has been designed to be user-friendly and easily accessible across different operating systems, including macOS, Windows, and Linux. The platform can be downloaded by users from the GitHub repository. 

###  1. Running MetaBioDetect on Windows
For Windows users, MetaBioDetect is available as a compiled executable file, allowing the software to be run without requiring additional installation or configuration. Users can simply double-click the .exe file to launch the application.
 [Download MetaBioDetect](https://github.com/ZahraKarimiBIX/MetaBioDetect/releases/download/MetaBioDetect/MetaBioDetect_21_09_2026.zip)
 
### 2. Running MetaBioDetect on Linux and macOS
For Linux and macOS users, MetaBioDetect can be run directly from the source code. It is recommended to use a Python virtual environment to isolate the software and its dependencies from other Python installations on the system. Follow the steps below to set up and run MetaBioDetect.

### Step 1: Create a virtual environment

First, navigate to the directory containing the MetaBioDetect source code and create a Python virtual environment using the following command:

python3 -m venv .venv

This creates a virtual environment named .venv within the MetaBioDetect directory. The virtual environment provides an isolated environment in which the required Python packages can be installed without affecting other Python projects or the system-wide Python installation.

### Step 2: Activate the virtual environment

After creating the virtual environment, activate it using:

source .venv/bin/activate

Once activated, the name of the virtual environment, typically (.venv), will appear at the beginning of the command-line prompt. This indicates that subsequent Python and package-management commands will use the virtual environment.

### Step 3: Install the required dependencies

With the virtual environment activated, install all Python packages required by MetaBioDetect using the requirements.txt file:
git clone https://github.com/ZahraKarimiBIX/MetaBioDetect.git 
cd MetaBioDetect
pip install -r requirements.txt

This command automatically installs the required dependencies and their compatible versions specified in the requirements.txt file.

### Step 4: Launch MetaBioDetect

Once the dependencies have been successfully installed, start the MetaBioDetect platform by running:

python3 MetaBarcoding.py

The MetaBioDetect platform will then launch, allowing users to access its available analysis and visualisation functions.
Note: The virtual environment must be activated each time MetaBioDetect is run from the source code. If the terminal session is closed or the virtual environment is deactivated, it can be reactivated by running:

source .venv/bin/activate

The above procedure provides a reproducible and isolated environment for running MetaBioDetect on Linux and macOS systems.


---

## 🚀 Features

- Adapter & primer trimming
- Read merging (paired-end support)
- Length and quality filtering
- Dereplication (unique sequence identification)
- Clustering (ASV and OTU)
- Remove chimeric reads 
- Taxonomic assignment using different Refernce database (online BLAST, local Blast, Local customised Refernce database)
- Step-by-step or full pipeline execution
- Intermediate file inspection and resumable workflows

---

## 📊 Workflow Overview

Raw Reads  
↓  
Adapter & Primer Trimming  
↓  
Read Merging (optional)  
↓  
Length Filtering  
↓  
Dereplication (Unique Sequences)  
↓  
Clustering (ASV and OTU)  
↓  
Remove Chimeric reads  
↓  
Taxonomy assignment  
↓  
MetaResult database  
↓  
Taxonomy Resolution
↓  
Saving and Visualising Results

Users can:
- Run the **entire workflow sequentially**
- Execute **individual steps independently**
- Inspect intermediate outputs and logs
- Resume interrupted analyses
- Taxonomy assignment and Resolution after processing data
---

## 🔧 Pipeline Steps

### 1. Adapter & Primer Trimming

Adapter and primer trimming can be performed in separate windows using MetaBioDetect, which integrates the functionality of Cutadapt with a user-friendly set of configurable parameters. **Configurable parameters:**
The available parameters include minimum read length selection, quality cutoff, maximum number of ambiguous bases (Max-N) allowed in a read, overlap length, and error rate. The minimum length parameter helps remove excessively short reads that may reduce downstream analysis accuracy. The quality cutoff parameter trims or filters low-quality bases and reads to improve overall sequence reliability. The Max-N parameter allows users to exclude reads containing more than a specified number of ambiguous “N” bases. In addition, overlap length defines the minimum overlap required between the read and the adapter or primer sequence for successful trimming, while the error rate parameter controls the maximum allowed mismatch rate during sequence matching.
The workflow also provides flexible output management options. Users can choose to discard untrimmed reads entirely or save them into a separate output file for further inspection and analysis. Furthermore, each preprocessing and processing section includes an “Other Comments” field, enabling users to add custom Cutadapt commands or additional parameters for more advanced analyses. During the adapter and primer trimming step, MetaBioDetect performs both filtering and trimming of sequencing reads based on the selected criteria, ensuring improved read quality and more reliable downstream bioinformatics analysis.


---

### 2. Merging

If the input file contains both forward and reverse reads, they can be merged using this option. Users can configure several parameters for the merging process. One of these parameters is the minimum overlap length, which defines the minimum number of overlapping bases required between the forward and reverse reads for successful merging. By default, the tool sets this value to 20 if the user does not specify a different value. Another parameter is the maximum overlap mismatches, which determines the maximum number of mismatched bases allowed within the overlapping region during merging. The default value for this parameter is 5 unless the user provides a custom setting.
**Parameters:**
- minimum overlap  
- maximum overlap  
- overlap identity  

---

### 3. Quality and Length Filtering
In this section, filtering can again be performed based on the quality and length of reads. This step is provided separately for users working with single-end sequence data rather than paired forward and reverse reads. Therefore, users can directly upload single-end sequencing files in this section and perform the required filtering and quality control analyses. This step is also useful for users who did not apply length or quality filtering during the previous trimming stages. Several configurable parameters are available to refine the filtering process.
The first parameter is the Maximum Expected Error, which defines the maximum number of expected sequencing errors allowed in a read. Reads exceeding this threshold are discarded to improve overall sequence quality.
Additional parameters include Minimum Length and Maximum Length, which allow users to retain reads only within a specified size range. Reads shorter or longer than the selected thresholds can be removed to improve the accuracy of downstream analyses. Another parameter, Maximum N Bases, allows users to specify the maximum number of ambiguous or unknown bases (N) permitted within a read.
In addition, a Minimum Quality Score parameter can be applied to filter or trim low-quality reads based on their Phred quality scores. This helps ensure that only high-confidence sequence reads are retained for subsequent analyses. Together, these filtering options provide flexibility for processing both single-end and previously unfiltered datasets, resulting in cleaner and more reliable data for downstream analysis.


---

### 4. Dereplication (Unique Sequences)

Dereplication refers to the process of grouping identical sequence reads into a single representative sequence while recording their abundance or zise in the dataset. This reduces redundancy and computational burden.  The input for this step is the final output file generated after preprocessing, including filtering and trimming stages. The output of this step consists of a set of unique reads, each annotated with a title that includes its abundance (size), where the size represents the number of times each identical read occurs in the dataset. This abundance information is important for downstream analyses, as it reflects the frequency of each sequence in the sample.

---

### 5. Clustering (ASV and OTU)
Clustering of unique sequences can be performed using either ASV or OTU approaches. In the ASV workflow, parameters such as min sequence size and size annotation mode are applied to control which sequences are retained for downstream analysis. The min sequence size defines the minimum abundance threshold for a sequence to be kept; for example, a value of 8 would remove any sequence represented fewer than eight times .
Another key setting is the size annotation mode, which determines how abundance values are handled during clustering. Choosing both size in and size out ensures that abundance counts from the input (derived during dereplication) are carried forward and summed through the clustering process, producing a final abundance that reflects both steps. In contrast, selecting only size out assigns abundance based solely on the clustering step, ignoring the original dereplication counts.

---

### 6.Remove chimeric reads
After the clustering step in the metabarcoding workflow, chimeric reads are usually removed. Following this step, the sequencing data are ready for taxonomic assignment.


---

### 7. Taxonomy Assignment

Taxonomy assignment can be performed using several options, depending on the user's preference. The available options include BLAST: Online Alignment, BLAST: Local Alignment, and Custom Database. The first two options enable taxonomy assignment using BLAST, either through an online alignment service or a locally downloaded BLAST database. The third option allows users to perform taxonomy assignment using their own locally created database.   

7-1. Taxonomy assignment using Blast database

The BLAST window for online alignment includes an option to select the desired database from the Database menu. Users can also specify parameters such as Organism, Percentage Identity, Maximum Target Sequences, and API Keys. The BLAST window for local alignment includes the same parameters; however, instead of selecting a database name, users must load a local database file before performing the analysis. The Organism parameter allows users to restrict searches to specific taxonomic groups, such as plants, animals, fungi, or any other categories supported by BLAST. The Percentage Identity parameter enables users to define the minimum sequence similarity required for reporting matches. The Maximum Target Sequences parameter determines the number of BLAST hits retained for each query sequence. This option is particularly important for taxonomic assignment because it influences the taxonomic resolution and the range of potential matches available for downstream analysis. For example, if the value is set to 30, the output will contain up to 30 BLAST hits for each query sequence, providing a broader set of candidate matches for taxonomy assignment. Users may also provide an Application Programming Interface (API) key to access BLAST services. Using an API key can help increase the number of requests allowed within a given time period and may improve the efficiency of large-scale analyses by reducing rate limitations imposed on anonymous users.
After configuring all required parameters, a database named MetaResult database is automatically created. This database serves as a central repository for all BLAST search results. As BLAST is executed for each sample, the corresponding sequence alignment records and taxonomy assignments are collected and stored in MetaResult database. By maintaining all BLAST results in a single database, users do not need to rerun BLAST analyses for samples that have already been processed. The stored results can be reused for downstream analyses, reducing computational time and ensuring consistent taxonomy assignments across projects. Additionally, the centralized database makes it easier to manage, query, and compare taxonomy results from multiple samples.

7-2. Taxonomy assignment using a custom database

For taxonomy assignment using a user-created local database, users can load their own reference database and specify the desired percentage identity threshold. In addition, the software provides an option to save assigned and unassigned reads in separate output files. This feature allows users to easily distinguish reads that were successfully assigned to taxa from those that could not be matched to any reference sequence in the database.
 
---

## 🧩 Flexibility & Execution Modes

### Run Full Pipeline Mode
In addition to the step-by-step workflow from raw input data to the final output, we have developed a sequential workflow option that can be executed within a single window. The sequential workflow automatically processes data from raw input files to the final output, significantly reducing the time and effort required to analyze large metabarcoding datasets. Alternatively, the step-by-step workflow allows users to run individual stages independently, providing greater flexibility in data processing. Such functionality is particularly valuable for quality control, troubleshooting, and result validation. In addition, analyses can be paused and resumed at any time, making it convenient to manage long-running workflows or revisit projects at a later stage. 
The sequential workflow allows users to load input files containing forward and reverse reads and perform all processing steps within a single interface. These steps include adapter and primer trimming, length and quality filtering, read merging, identification of unique sequences, sequence clustering, chimera removal, and taxonomic assignment. Through the available tabs and settings panels, users can specify the parameters for each processing stage and execute the entire workflow in a single run. Users can also select or deselect individual workflow steps according to their requirements, allowing them to remove unnecessary steps from the pipeline.
 
---

### 8. MetaResult Database and Taxonomy Resolution Analysis

One of the most useful and important features of MetaBioDetect is its ability to create an interactive database following taxonomic assignment named MetaResult Database. This database provides a dedicated interface for exploring, filtering, and analyzing taxonomic assignment results. The interface consists of four main sections.
Section A contains several filtering and selection options, including Sample Name, Top Hits, Identity Threshold, and Assigned/Unassigned Reads. The Sample Name menu allows users to select individual samples or multiple samples loaded into the database for downstream analyses.
The Top Hits option is particularly important for taxonomic resolution analysis. During taxonomic assignment , users can specify the maximum number of BLAST hits to retain for each query sequence. For example, if the maximum number of target hits is set to 30, the database will store up to 30 BLAST matches for each read. Within the database interface, users can choose to display any number of hits, from 1 up to the maximum value specified during taxonomic assignment. Users can also adjust the identity threshold according to the value used during the BLAST search or reference database comparison. In addition, by selecting the checkbox labeled Unassigned, users can choose to display unassigned reads alongside assigned reads, allowing both categories to be included in the results table for further analysis.
Section B contains one of the unique features of MetaBioDetect: taxonomic resolution analysis. The first option in this section is Aggregate Results, which is used to determine the most reliable taxonomic level for each read based on all retained BLAST hits. For example, if 30 top hits have been retained for a read, the software examines all 30 hits. If all hits correspond to the same species, the read is assigned at the species level. If species assignments differ but all hits belong to the same genus, the read is assigned at the genus level. Similarly, if genus assignments differ but all hits belong to the same family, the read is assigned at the family level. This process continues through higher taxonomic ranks as necessary.
Following taxonomic resolution analysis, two additional columns are added to the results table (Section C), namely Taxa_Level and Taxa_Name. These columns indicate the resolved taxonomic rank and the corresponding taxon name for each read. Reads assigned to the same taxon are subsequently aggregated, allowing counts and abundances to be summarized at the selected taxonomic level.
The second option in Section B is Calculate Abundance. After aggregation, users can calculate the relative abundance of reads as percentages, enabling quantitative community analyses.

Section C displays the main results table, with one table generated for each sample or analysis run. The table contains sequence information, BLAST match results, and taxonomic classifications. Each row includes details such as read identifiers, read abundance, nucleotide sequences, accession numbers, taxonomic classifications ranging from species to kingdom/domain, E-values, percentage identities, alignment lengths, gap counts, and other BLAST-related metrics.The score represents a raw measure of alignment quality based on matches, mismatches, and gaps, where higher values indicate better alignments. The E-value (expect value) estimates the probability that an observed match could occur by chance in a database search, with lower values indicating more statistically significant and reliable hits. Identities refer to the number or proportion of exact nucleotide or amino acid matches between the read and reference sequence, often expressed as percent identity, which reflects overall sequence similarity across the aligned region. Gaps indicate insertions or deletions introduced to optimize alignment, with fewer gaps generally suggesting a closer evolutionary relationship. The bit score is a normalized version of the raw score that allows comparisons across different searches and databases, where higher values indicate stronger matches. Additional parameters such as read abundance reflect how frequently a sequence occurs in the dataset, while accession numbers uniquely identify reference sequences in public databases. Together with taxonomic classification (from domain to species level, including TaxID and scientific name), these metrics provide a comprehensive framework for assessing the reliability and biological meaning of each read assignment.
The contents of the table are dynamically updated according to the parameters selected in Sections A and B, allowing users to view and analyse results based on their chosen search criteria and filtering settings. For example, changing the number of displayed top hits from 30 to 1 will show only the first hit for each read, while increasing the identity threshold from 97% to 100% will restrict the displayed results to perfect matches.
After taxonomic resolution and aggregation, the table is updated to reflect the processed results. Users can save outputs both before and after applying these analyses, allowing intermediate and final results to be exported through the File menu for further investigation.
Section D provides summary statistics for assigned and unassigned taxa, which are critical for evaluating taxonomic assignment performance. The sequence identity threshold is one of the most influential parameters affecting assignment success. In many metabarcoding studies, a threshold of 97% sequence identity is commonly used. Unassigned reads are sequences for which no suitable BLAST match is identified under the selected criteria. By adjusting the identity threshold, users can immediately observe changes in the numbers and percentages of assigned and unassigned reads within this section, facilitating assessment of the effects of different assignment parameters.
The Summary sections in both screenshots demonstrate differences in the numbers of assigned and unassigned reads based on the applied identity threshold.

After completing all analyses, including taxonomic resolution, aggregation, and percentage abundance calculation, a summary matrix is generated. This matrix contains the columns Taxa_Level, Taxa_Name, Abundance, and Percentage Abundance. The resulting table provides a concise summary of the taxonomic composition of the sample and can be directly used for downstream visualization and plotting. By default, the table is sorted by taxonomic level. If users prefer to sort the data by abundance, they can do so after exporting the table as a CSV file.
Important User Note: The Maximum Target Sequences (Top Hits) parameter has a significant impact on taxonomy resolution. If this value is set to 1, only the single best BLAST hit will be retrieved for each query sequence. Consequently, taxonomy resolution will simply reflect the taxonomy of that top hit, which is often reported at the species level and does not provide sufficient information for robust consensus-based taxonomic assignment.
For more accurate and reliable taxonomy resolution, multiple BLAST hits should be retrieved for each sequence. This allows the taxonomy resolution algorithm to compare several high-scoring matches and assign taxonomy at the most appropriate taxonomic rank based on the collective evidence. The optimal number of target sequences depends on the objectives of the study and the diversity of the reference database. However, a value of 20–30 maximum target sequences is generally recommended as a suitable default for most metabarcoding analyses, as it provides enough information for reliable taxonomic inference while maintaining computational efficiency.


---

### 9.Exporting Data from MetaResult database
To export data from this section, use the Export Results. Export Raw Data option, which includes the raw taxonomy assignment file. If you modify parameters such as the number of top hits, percentage identity, or other filtering criteria, you can save the updated results using the Filtered Results option available in this menu. Options are also provided for exporting taxonomy resolution results, aggregated results, and abundance percentages.

The File section of MetaResult database allows users to load taxonomy assignment result files for taxonomy resolution, further analysis and export processed results as CSV files. The available export options include raw taxonomic assignment results, filtered taxonomic assignment results, taxonomy resolution results, and taxon abundance percentages for downstream analyses and visualization. These export options provide flexibility for users to perform additional statistical analyses, generate custom visualisations, or integrate the results with other bioinformatics tools. The Plot Results section provides several visualization options for displaying abundance data at the species, genus, and family levels. By selecting the desired option in the Plot Results section, users can generate different types of plots, including bar plots, treemaps, and pie charts, showing the top species, top genera, and top families within a sample.
The generated plots are interactive and support features such as box selection and zooming. Users can save the interactive results as an HTML file, which preserves all generated visualizations and interactive functionalities. In addition, individual plots can be exported directly as PNG images using the "Download plot as PNG" option.

---

### 10.Tools section in MetaBioDetect 
The next menu in the main window of MetaBioDetect is the Tools section. This section contains two options: Sample Repository Manager and BLAST Database Management.

The Sample Repository Manager allows users to import MetaResult databases from one or multiple samples, edit sample names, and delete samples when required. This feature is particularly useful when samples need to be renamed or organised after analysis. The Sample Repository Manager is especially valuable when taxonomy assignment has been performed using BLAST or a custom reference database for a large number of samples, resulting in multiple MetaResult databases. Instead of loading each MetaResult file individually, users can import them together into the repository, where sample names can be edited or samples can be removed as needed. Once the MetaResult databases have been loaded, all available samples will appear in MetaResult database, section A. Clicking on a sample name displays the corresponding sample data. This approach saves considerable time and effort by allowing multiple MetaResult databases to be managed and accessed from a single location rather than uploading them one by one.
The second option in the Tools section is BLAST Database Management, which facilitates the download of required NCBI BLAST databases, such as nr and nt. The Database Name menu, which contains a list of all available databases. Users can either download databases from the NCBI BLAST website or use MetaBioDetect to conveniently download their preferred NCBI databases.

---



### 11.Help Section in MetaBioDetect
The complete user manual for MetaBioDetect can be accessed and downloaded through the Help menu by selecting the User Guide option. In addition, the About MetaBioDetect option, available under the Help menu, provides an overview of the software, including its purpose, key functionalities, version information, and developer details. This section offers users a brief introduction to MetaBioDetect and its applications in biological data analysis .


---


---

## 🖥️ GUI Features

- Modular workflow execution  
- Parameter customization at each step  
- Intermediate result inspection  
- Logging support  
- Resume interrupted runs  

---

## ⚙️ Customization

Each stage includes:
- Adjustable parameters  
- Optional command extensions via “Other comment”  
- Independent execution capability  

---

## ⚠️ Notes & Considerations

- UNOISE defaults are strict and may remove rare sequences  
- Quality filtering is partially duplicated across steps  
