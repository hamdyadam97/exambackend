"""Rule-based filing of questions into sections, topics and (when missing) a subject.

No AI: keyword patterns on the question, its options and explanation. A topic hit decides the section;
otherwise the strongest section keywords; otherwise a default section for the question's subject.
Candidate sections are limited to the question's field (dentistry, nursing, anesthesia, medicine).
"""
import html
import re

from apps.content.taxonomy import SECTIONS

# ------------------------------------------------------------------ keywords
# Extra words for topics (the topic's own name is always used as well).
TOPIC_WORDS = {
    'Obstructive Lung Disease': r'copd|asthma|emphysema|chronic bronchitis|bronchiectasis|spirometr|fev1',
    'Restrictive Lung Disease': r'restrictive',
    'Interstitial Lung Disease': r'pulmonary fibrosis|interstitial|sarcoidosis|pneumoconiosis',
    'Lung Neoplasms': r'lung cancer|bronchogenic|small cell carcinoma|mesothelioma|pancoast|lung (mass|nodule)',
    'Pulmonary Vasculature Disease': r'pulmonary hypertension|cor pulmonale',
    'Pulmonary Embolism': r'pulmonary embol|\bpe\b|d-dimer|wells score',
    'Pulmonary Edema': r'pulmonary oedema|pulmonary edema',
    'Pleural Effusion': r'pleural effusion|thoracentesis|light.s criteria|empyema',
    'Pneumothorax': r'pneumothorax',
    'Pneumonia': r'pneumonia|consolidation',
    'Upper Respiratory Tract Infections': r'pharyngitis|tonsillitis|sinusitis|common cold|croup|epiglottitis|otitis',
    'Lower Respiratory Tract Infections': r'bronchiolitis|bronchitis|tuberculosis|\btb\b',
    'Neonatal Respiratory Conditions': r'respiratory distress syndrome|surfactant|transient tachypnea|meconium aspiration',
    'Sleep Disorders': r'sleep apnea|sleep apnoea|insomnia|narcolepsy',
    'Ischemic Heart Disease': r'angina|coronary artery disease|ischemic heart|ischaemic heart',
    'Acute Coronary Syndrome': r'acute coronary|stemi|nstemi|troponin|unstable angina',
    'Myocardial Infarction': r'myocardial infarction|\bmi\b|\binfarction',
    'Congestive Heart Failure': r'heart failure|\bchf\b|ejection fraction|bnp',
    'Arrhythmias & ECG': r'arrhythmi|atrial fibrillation|flutter|tachycardia|bradycardia|heart block|\becg\b|\bekg\b|qt interval|wolff',
    'Cardiomyopathies': r'cardiomyopathy|myocarditis',
    'Pericardial Disease': r'pericardi|tamponade',
    'Valvular Heart Disease': r'stenosis of the (aortic|mitral)|aortic stenosis|mitral (stenosis|regurgitation|valve)|aortic regurgitation|murmur|endocarditis|valv',
    'Congenital Heart Disease': r'tetralogy|ventricular septal|atrial septal|patent ductus|coarctation|transposition|\bvsd\b|\basd\b|\bpda\b',
    'Arterial Diseases & Hypertension': r'hypertension|blood pressure|aortic dissection|aneurysm|peripheral arter|claudication',
    'Venous Diseases': r'deep vein|\bdvt\b|varicose|venous',
    'Esophageal Diseases': r'oesophag|esophag|achalasia|barrett|gerd|reflux|dysphagia',
    'Stomach Diseases': r'gastritis|gastroparesis|pyloric',
    'Peptic Ulcer': r'peptic ulcer|h\.? ?pylori|helicobacter',
    'Duodenal Ulcer': r'duodenal ulcer',
    'Gastric Cancer': r'gastric (cancer|carcinoma|adenocarcinoma)|stomach cancer',
    'Small Intestine Diseases': r'celiac|coeliac|malabsorption|small bowel',
    'Colon Diseases': r'colon|colorectal|colitis|polyp',
    'Inflammatory Bowel Disease': r'crohn|ulcerative colitis|inflammatory bowel|\bibd\b',
    'Diverticulitis': r'diverticulitis',
    'Diverticular Disease & Angiodysplasia': r'diverticul|angiodysplasia',
    'Rectal Disease': r'rectal|rectum|hemorrhoid|haemorrhoid',
    'Perianal Diseases': r'anal fissure|fistula.in.ano|perianal|pilonidal',
    'Appendix Diseases': r'appendic',
    'Bowel Obstruction and Perforation': r'bowel obstruction|intestinal obstruction|volvulus|perforat|ileus',
    'Functional Gastrointestinal Disorders': r'irritable bowel|\bibs\b|functional dyspepsia|constipation',
    'GI Bleeding': r'gi bleed|gastrointestinal bleed|hematemesis|melena|haematemesis|melaena|variceal',
    'Liver Diseases': r'hepatitis|cirrhosis|liver|hepatic|ascites|wilson|hemochromatosis',
    'Jaundice': r'jaundice|bilirubin',
    'Gallbladder Diseases': r'gallbladder|gallstone|cholecyst|cholangitis|biliary|murphy',
    'Pancreas Diseases': r'pancrea',
    'Salivary Gland Diseases': r'salivary|parotid|sialo',
    'Renal Failure': r'renal failure|kidney injury|\baki\b|\bckd\b|chronic kidney|dialysis|uremi|creatinine',
    'Proteinuria & Hematuria': r'proteinuria|hematuria|haematuria',
    'Glomerular Disease': r'glomerul|iga nephropathy|alport',
    'Nephrotic Syndrome': r'nephrotic',
    'Tubulointerstitial Disease': r'interstitial nephritis|tubular necrosis|renal tubular acidosis',
    'Renal Cystic Disease': r'polycystic kidney|renal cyst',
    'Renal-Vascular Disease': r'renal artery stenosis|renovascular',
    'Renal Stones & Obstruction': r'renal stone|kidney stone|nephrolithiasis|urolithiasis|renal colic|hydronephrosis|calculi',
    'Renal Neoplasms': r'renal cell carcinoma|wilms|kidney cancer|bladder cancer',
    'Renal Infections': r'pyelonephritis|urinary tract infection|\buti\b|cystitis',
    'Bladder Diseases': r'bladder',
    'Prostate Disease': r'prostat|\bbph\b|\bpsa\b',
    'Electrolyte Disorders': r'hyponatr|hypernatr|hypokal|hyperkal|hypocalc|hypercalc|hypomagnes|electrolyte|sodium|potassium',
    'Acid-Base Disorders': r'acidosis|alkalosis|anion gap|acid.base|\babg\b|arterial blood gas',
    'Fluid Replacement': r'fluid (replacement|resuscitation|therapy)|normal saline|ringer|maintenance fluid|dehydration',
    'Anticoagulation': r'warfarin|heparin|anticoagul|\binr\b|apixaban|rivaroxaban|dabigatran',
    'Platelets & Coagulopathies': r'platelet|thrombocytopen|\bitp\b|\bttp\b|hemophilia|haemophilia|von willebrand|\bdic\b|coagul|bleeding time',
    'Myeloproliferative Diseases': r'polycythemia|polycythaemia|myelofibrosis|thrombocythemia|leukemia|leukaemia|\bcml\b|\baml\b|\bcll\b',
    'Plasma Cell Disorders': r'multiple myeloma|myeloma|waldenstr|amyloidosis',
    'Hodgkin Lymphoma': r'hodgkin|reed.sternberg',
    'Non-Hodgkin Lymphoma': r'non.hodgkin|lymphoma|burkitt',
    'Spleen Diseases': r'splen',
    'Blood Transfusion': r'transfusion|blood product|packed red',
    'Chemotherapy': r'chemotherap|cisplatin|doxorubicin|vincristine|methotrexate|cyclophosphamide',
    'Thyroid Diseases': r'thyroid|hypothyroid|thyroxine|\btsh\b|goiter|goitre',
    'Hyperthyroidism': r'hyperthyroid|thyrotoxicosis',
    'Graves Disease': r'graves',
    'Parathyroid Diseases': r'parathyroid|\bpth\b',
    'Pituitary Diseases': r'pituitar|acromegaly|prolactin|diabetes insipidus|siadh|cushing.s disease',
    'Adrenal Diseases': r'adrenal|addison|cushing|pheochromocytoma|aldosteron|cortisol|congenital adrenal',
    'Bone Disorders': r'osteoporosis|osteomalacia|rickets|paget',
    'Metabolic Disorders': r'diabetes|diabetic|insulin|hypoglyc|hyperglyc|dka|ketoacidosis|hba1c|metformin|obesity|lipid|cholesterol',
    'Nutritional Disorders': r'vitamin|malnutrition|kwashiorkor|marasmus|scurvy|beriberi|pellagra',
    'Connective Tissue Diseases': r'lupus|\bsle\b|scleroderma|systemic sclerosis|sjogren|dermatomyositis|polymyositis',
    'Crystal-Induced Arthritis': r'gout|pseudogout|uric acid|urate',
    'Vasculitis': r'vasculitis|arteritis|kawasaki|henoch|wegener|granulomatosis with polyangiitis|polyarteritis|behcet',
    'Osteoarthritis': r'osteoarthritis',
    'Rheumatoid Arthritis': r'rheumatoid',
    'Infectious Arthritis': r'septic arthritis|infectious arthritis|osteomyelitis',
    'Autoimmune Diseases': r'autoimmun',
    'Granulomatous Diseases': r'granuloma',
    'Immunodeficiency Disorders': r'immunodeficien|agammaglobulin|digeorge|wiskott|\bscid\b|complement deficiency',
    'Allergic Reactions': r'anaphyla|allerg|urticaria|angioedema',
    'Movement Disorders': r'parkinson|tremor|chorea|huntington|dystonia',
    'Altered Mental Status': r'delirium|dementia|alzheimer|confusion|coma|glasgow',
    'Demyelinating Disease': r'multiple sclerosis|demyelinat|guillain',
    'Neuromuscular Disease': r'myasthenia|muscular dystrophy|neuropathy|\bals\b|motor neuron',
    'Spinal Cord Diseases': r'spinal cord|cauda equina|myelopathy',
    'Seizures': r'seizure|epilep|convulsion|status epilepticus|febrile convulsion',
    'Meningitis & Encephalitis': r'meningitis|encephalitis|lumbar puncture',
    'Brain Tumor': r'brain tumou?r|glioma|glioblastoma|meningioma|medulloblastoma',
    'Brain Hemorrhage': r'subarachnoid|intracerebral|haemorrhagic stroke|hemorrhagic stroke|stroke|cerebrovascular|tia\b',
    'Head Trauma': r'head (injury|trauma)|epidural hematoma|subdural|concussion',
    'Basal Skull Fracture': r'basal skull|battle.s sign|raccoon eyes',
    'Brain Death': r'brain death|brainstem death',
    'Neural Tube Defects': r'neural tube|spina bifida|anencephaly|myelomeningocele',
    'Acute Flaccid Paralysis': r'flaccid paralysis|poliomyelitis|\bpolio\b',
    'Infantile Hypotonia': r'hypotonia|floppy infant',
    'Bacterial Infections': r'bacteri|staphylococc|streptococc|clostridi|e\. ?coli|salmonell|shigell|brucell|typhoid',
    'Viral Infections': r'viral|virus|measles|mumps|rubella|varicella|herpes|influenza|covid',
    'Fungal Infections': r'fungal|candida|aspergill|tinea|cryptococc',
    'Parasitic Infections': r'parasit|malaria|plasmodium|helminth|giardia|amoeb|leishmania|schistosom|worm',
    'Zoonotic Diseases': r'zoono|rabies|brucell|anthrax|q fever',
    'Sepsis': r'sepsis|septic',
    'Septic Shock': r'septic shock',
    'Fever': r'fever of unknown|pyrexia',
    'HIV': r'\bhiv\b|\baids\b|cd4',
    'Sexually Transmitted Diseases (STD)': r'syphilis|gonorrh|chlamydia|sexually transmitted|\bstd\b|\bsti\b',
    'GI Infections': r'gastroenteritis|diarrh|cholera|food poisoning',
    'Genitourinary Infections': r'urethritis|vaginitis|vaginosis|trichomon',
    'Ear Infections': r'otitis|mastoiditis',
    'Antenatal Care': r'antenatal|prenatal|booking visit|folic acid',
    'Physiological Changes in Pregnancy': r'physiological changes in pregnancy|in pregnancy',
    'Pregnancy & Labor': r'labou?r|delivery|cesarean|caesarean|partograph|bishop|cervical dilat',
    'Assisted Vaginal Delivery': r'forceps|vacuum|ventouse',
    'Ectopic Pregnancy': r'ectopic',
    'Antepartum Hemorrhage': r'placenta previa|placental abruption|abruptio|antepartum ha?emorrhage',
    'Postpartum Hemorrhage': r'postpartum ha?emorrhage|\bpph\b|uterine atony',
    'Hypertensive Disorders of Pregnancy': r'pre.?eclampsia|eclampsia|hellp|gestational hypertension',
    'Gestational Trophoblastic Neoplasia': r'molar pregnancy|hydatidiform|choriocarcinoma|trophoblast',
    'Puerperium': r'puerper|postpartum|lactation|breastfeed',
    'Multiple Pregnancy': r'twin|multiple pregnancy',
    'Placental Disorders': r'placenta',
    'Oligohydramnios and Polyhydramnios': r'hydramnios|amniotic fluid',
    'Rh Incompatibility': r'\brh\b|rhesus|anti.d|isoimmun',
    'Drugs in Pregnancy': r'teratogen|in pregnancy.*(drug|safe)|(drug|safe).*in pregnancy',
    'Pelvic Inflammatory Disease': r'pelvic inflammatory|\bpid\b|salpingitis',
    'Urinary Incontinence': r'incontinence',
    'Genital Prolapse': r'prolapse',
    'Uterine Fibroid': r'fibroid|leiomyoma',
    'Endometriosis': r'endometriosis|adenomyosis',
    'Infertility': r'infertil|ivf',
    'Amenorrhea': r'amenorrh',
    'Abnormal Uterine Bleeding': r'abnormal uterine bleeding|dysfunctional uterine|\baub\b',
    'Menorrhagia': r'menorrhagia|heavy menstrual',
    'Menopause': r'menopaus|hormone replacement',
    'Polycystic Ovary Syndrome (PCOS)': r'polycystic ovar|\bpcos\b',
    'Ovarian Disorders': r'ovarian cyst|ovarian torsion',
    'Ovarian Cancer': r'ovarian (cancer|carcinoma|tumou?r)|ca.?125',
    'Endometrial Cancer': r'endometrial (cancer|carcinoma|hyperplasia)',
    'Cervical Cancer': r'cervical (cancer|carcinoma|intraepithelial)|pap smear|\bhpv\b|colposcop',
    'Contraception': r'contracepti|\biud\b|oral contraceptive|condom',
    'Testicular Diseases': r'testic|scrot|hydrocele|varicocele|cryptorchid',
    'Embryology': r'embryolog|embryo',
    'Pre- and Post-Operative Management': r'post.?operative|pre.?operative|perioperative|wound infection|surgical site',
    'Abdominal Trauma': r'abdominal trauma|blunt abdominal|fast scan|splenic rupture',
    'Hernia': r'hernia',
    'Breast Diseases': r'breast|mammogra|fibroadenoma|mastitis',
    'Wounds, Ulcers & Cysts': r'wound|ulcer|cyst|abscess|burn',
    'Bariatric Surgery': r'bariatric|gastric bypass|sleeve gastrectomy',
    'Vascular Surgery': r'vascular surgery|endarterectomy|amputation|limb ischemia|limb ischaemia',
    'Chest Trauma': r'chest trauma|flail chest|hemothorax|haemothorax|rib fracture|tension pneumothorax',
    'Intussusception': r'intussusception',
    'Congenital GI Defects': r'pyloric stenosis|hirschsprung|duodenal atresia|tracheoesophageal|malrotation|gastroschisis|omphalocele',
    'Neonatology': r'newborn|neonat|apgar|preterm|premature',
    'Congenital Conditions': r'congenital|down syndrome|turner|klinefelter|trisomy',
    'Disorders of Growth': r'short stature|failure to thrive|growth (hormone|chart|delay|retardation)|tall stature',
    'Developmental Assessment': r'milestone|developmental|smiles|walks|sits',
    'Vaccines': r'vaccin|immuniz|immunis',
    'Genetic Disorders': r'genetic|autosomal|x.linked|chromosom|mutation|inherit',
    'Orthopedic Fractures': r'fracture|dislocation',
    'Orthopedic Tumors': r'osteosarcoma|ewing|bone tumou?r',
    'Bone and Joint Disorders': r'joint|ligament|tendon|scoliosis|club ?foot|hip dysplasia|perthes|slipped capital',
    'Dermatitis': r'dermatitis|eczema|psoriasis|acne',
    'Skin Lesions': r'rash|skin lesion|macule|papule|vesicle|pemphig|vitiligo',
    'Skin Cancer': r'melanoma|basal cell carcinoma|squamous cell carcinoma of the skin',
    'Depression': r'depress|suicid|bipolar|mania|antidepressant|ssri',
    'Eye Infections': r'conjunctivitis|keratitis|uveitis|endophthalmitis',
    'Drug-Induced Diseases': r'side effect|adverse effect|drug.induced|toxicity of',
    'Adverse Drug Reactions': r'drug reaction|stevens.johnson',
    'Immunosuppressants (Cyclosporine)': r'cyclosporin|tacrolimus|immunosuppress',
    'Poisoning': r'poison|overdose|toxicolog|antidote|paracetamol|acetaminophen|organophosph',
    'IV Anesthesia': r'propofol|ketamine|thiopental|etomidate|induction agent',
    'Obstetric Anesthesia': r'epidural|spinal ana?esthesia.*(labou?r|cesarean|caesarean)|obstetric ana?esthesia',
    'Liver Physiology in Anesthesia': r'hepatic (blood flow|metabolism).*ana?esthe',
    'Local Anesthesia': r'local ana?esthe|lidocaine|lignocaine|bupivacaine|nerve block',
    'Head and Neck Anatomy': r'mandib|maxill|trigeminal|facial nerve|tmj|temporomandibular',
    'Oral Physiology': r'saliva|mastication|taste',
    'Oral Pathology': r'oral (lesion|pathology|cancer)|leukoplakia|lichen planus|ameloblastoma|odontogenic',
    'Dental Anatomy and Oral Histology': r'enamel|dentin|dentine|cementum|pulp|odontoblast|ameloblast',
    'Dental Materials': r'amalgam|composite|cement|impression material|alloy|resin|glass ionomer',
    'Prosthodontics': r'denture|crown|bridge|prosthes|implant|abutment',
    'Occlusion': r'occlusion|malocclusion|bite',
    'Endodontic Surgery': r'root canal|endodont|apicectomy|periapical',
    'Oral and Maxillofacial Surgery': r'extraction|third molar|impacted|alveolar osteitis|dry socket',
    'Dental Radiology': r'radiograph|x.ray|panoramic|periapical film|bitewing',
    'Infection Control': r'infection control|steriliz|sterilis|autoclave|disinfect|hand hygiene|isolation',
    'Periodontics': r'periodont|gingiv|plaque|calculus|scaling',
    'Cleft Lip and Palate': r'cleft',
    'Spina Bifida': r'spina bifida',
    'Hirschsprung Disease': r'hirschsprung',
    'Verbal Reasoning': r'synonym|antonym|analogy|meaning of',
    'Numerical Reasoning': r'\d+ ?%|percent|ratio|average|how many|calculate',
    'Logical Reasoning': r'series|pattern|next number|odd one',
    'Stoichiometry': r'mole|molar|empirical formula|stoichiometr|percent yield|limiting reagent',
    'Chemical Bonding & Structure': r'bond|lewis|hybridi|vsepr|electronegativ|orbital',
    'Thermochemistry': r'enthalpy|entropy|gibbs|exothermic|endothermic|calorimet',
    'Solutions & Equilibrium': r'equilibrium|\bph\b|buffer|molarity|titration|solubility',
    'Chemical Nomenclature': r'the name of|named|nomenclature',
    'Organic Chemistry': r'alkane|alkene|alcohol|ester|aldehyde|ketone|benzene|isomer|organic',
    'Cell Biology': r'cell membrane|organelle|mitochondri|ribosome|cell cycle|mitosis|meiosis',
    'Molecular Biology': r'\bdna\b|\brna\b|transcription|translation|replication|codon',
    'Ecology & Evolution': r'ecosystem|evolution|natural selection|population',
    'Plant & Animal Biology': r'photosynth|chlorophyll|plant|cyanobacteria',
}

# Section words (used when no topic matched).
SECTION_WORDS = {
    'Respiratory System': r'lung|pulmonary|respiratory|bronch|pleura|dyspnea|dyspnoea|cough|wheez',
    'Cardiovascular System': r'cardiac|heart|coronary|aort|myocard|arter',
    'Gastrointestinal System': r'abdominal pain|bowel|gastro|intestin|stomach|liver|hepat|vomit',
    'Renal and Urinary System': r'renal|kidney|urin|nephr|bladder',
    'Fluids and Electrolytes': r'fluid|electrolyte|sodium|potassium',
    'Hematology': r'anemia|anaemia|hemoglobin|haemoglobin|blood count|thalass|sickle|iron deficiency|leukocyt|lymphocyt',
    'Endocrine': r'hormone|endocrin|gland|diabet|thyroid',
    'Rheumatology': r'arthritis|joint pain|rheumat',
    'Immunology': r'immun|antibod|antigen|hypersensitivity',
    'Neurology': r'neuro|nerve|headache|migraine|brain|cerebr|weakness|paralysis|reflex',
    'Infectious Diseases': r'infect|antibiotic|fever|culture',
    'Reproductive System': r'pregnan|uter|ovar|vagin|menstru|gestation|obstetric|gyn|fetal|foetal',
    'General Surgery': r'surgery|surgical|operation|laparotom|incision|suture|anastomos',
    'Pediatrics': r'infant|child|newborn|neonat|toddler',
    'Musculoskeletal System': r'bone|muscle|fracture|orthop|joint',
    'Dermatology': r'skin|dermat|rash',
    'Psychiatry': r'psychiat|anxiety|schizo|psychosis|personality|hallucinat|delusion',
    'Ophthalmology': r'\beye\b|vision|visual|retin|glaucoma|cataract|cornea|optic',
    'ENT (Otorhinolaryngology)': r'\bear\b|hearing|nasal|nose|throat|larynx|tonsil|sinus|vertigo|tinnitus',
    'Pharmacology': r'\bdrug\b|mechanism of action|pharmacolog|dose|inhibitor|agonist|antagonist',
    'Forensic Medicine and Toxicology': r'forensic|autopsy|post.mortem|rigor mortis|toxic',
    'Emergency Medicine': r'emergency|resuscitat|\bcpr\b|trauma|shock',
    'Public Health': r'public health|epidemiolog|prevalence|incidence|screening|sensitivity|specificity|odds ratio|relative risk',
    'Biochemistry': r'enzyme|metabolism|glycolysis|krebs|amino acid|protein synthesis|biochem',
    'Genetics': r'gene|genetic|chromosom|inherit',
    'Anatomy': r'anatom|artery supplies|innervat|muscle attach|foramen|ligament',
    'Physiology': r'physiolog|cardiac output|action potential|membrane potential|renal clearance|gfr',
    'Pathology': r'patholog|necrosis|apoptosis|inflammation|neoplasia|histopatholog',
    'Microbiology': r'bacteria|virus|gram.positive|gram.negative|microbio|culture|spore',
    'Radiology & Nuclear Medicine': r'x.ray|\bct\b|\bmri\b|ultrasound|radiolog|scan',
    'Medical Ethics and Law': r'ethic|consent|confidential|autonomy|beneficence|malpractice',
    'Medical Terminology': r'suffix|prefix|term meaning|terminology|root word',
    'Clinical Anesthesia': r'ana?esthe|intubat|airway|muscle relaxant|neuromuscular block|sedation|inhalational',
    'Anesthesia Physics and Equipment': r'vapori[sz]er|flowmeter|circuit|capnograph|oximet|cylinder|monitoring',
    'Regional Anesthesia': r'nerve block|plexus|spinal|epidural|regional',
    'Cardiac Anesthesia': r'cardiopulmonary bypass|cardiac surgery',
    'Thoracic Anesthesia': r'one.lung|double.lumen|thoracic',
    'Pediatric Anesthesia': r'(child|infant|neonat|pediatric|paediatric).*ana?esth|ana?esth.*(child|infant|neonat)',
    'Orthopedic and Trauma Anesthesia': r'tourniquet|fat embolism|orthopa?edic',
    'Dental Basic Sciences': r'physiolog|anatom|biochem|vitamin|microbio',
    'Oral Biology and Pathology': r'oral|enamel|dentin|tooth development|odontogenic|lesion',
    'Clinical Dentistry': r'tooth|teeth|dental|denture|crown|cavity|caries|restoration|filling|extraction|root canal',
    'Diagnosis and Non-Surgical Therapy': r'diagnos|treatment plan|non.surgical',
    'Allergic, Metabolic and Infection-Related Emergencies': r'emergenc|syncope|anaphyla|hypoglyc|seizure|angina',
    'Arterial Blood Gases and Acid-Base Balance': r'\babg\b|blood gas|acidosis|alkalosis|\bph\b|pco2|hco3',
    'CPR and Chest Tube': r'\bcpr\b|chest tube|cardiac arrest|resuscitat|compression',
    'ECG Interpretation and Arrhythmia': r'\becg\b|\bekg\b|rhythm|arrhythmi|fibrillation|tachycardia',
    'IV Fluids': r'\biv\b|intravenous|infusion|drip|fluid',
    'Surgical and Post-Operative Care': r'post.?operative|pre.?operative|surgery|wound|drain|incision',
    'Pediatric Congenital Anomalies': r'cleft|spina bifida|hirschsprung|intussusception|congenital',
    'Nervous System and Special Senses': r'neuro|glasgow|\bgcs\b|intracranial|\bicp\b|seizure|stroke|eye|ear',
    'Multisystem': r'multi.?organ|burn|shock|sepsis',
    'Prenatal Care': r'pregnan|prenatal|antenatal|fetal|foetal|labou?r|postpartum',
    'Physical Assessment': r'assessment|inspection|palpation|auscultation|vital sign',
    'Quality and Safety': r'safety|incident|fall|error|quality|infection control|isolation|\bppe\b',
    'Nursing Management': r'delegat|leadership|manager|prioriti|assignment|charge nurse|shift report',
    'Fundamentals of Nursing': r'nursing process|nurse should|nurse|position|hygiene|bed|documentation',
    'Pain Management': r'pain (assessment|management|scale)|analges|opioid',
    'General Chemistry': r'chemical|reaction|compound|element|atom|molecule|gas law|g/mol',
    'General Physics': r'velocity|acceleration|force|energy|newton|joule|wave|current|voltage',
    'General Biology': r'cell|organism|species|biology|photosynth',
    'Aptitude (IQ)': r'synonym|antonym|analogy|series|next number|odd one|which word',
    'Urology': r'urolog|prostat|bladder|testic|scrot|urethr',
}

# Sections each field may use.
DENTAL_SECTIONS = {'Dental Basic Sciences', 'Oral Biology and Pathology', 'Clinical Dentistry',
                   'Diagnosis and Non-Surgical Therapy', 'Allergic, Metabolic and Infection-Related Emergencies',
                   'Pharmacology', 'Microbiology', 'Anatomy', 'Physiology', 'Pathology', 'Biochemistry'}
NURSING_SECTIONS = {'Arterial Blood Gases and Acid-Base Balance', 'CPR and Chest Tube', 'ECG Interpretation and Arrhythmia',
                    'IV Fluids', 'Surgical and Post-Operative Care', 'Pediatric Congenital Anomalies',
                    'Nervous System and Special Senses', 'Multisystem', 'Prenatal Care', 'Physical Assessment',
                    'Quality and Safety', 'Nursing Management', 'Fundamentals of Nursing', 'Pain Management',
                    'Respiratory System', 'Cardiovascular System', 'Gastrointestinal System', 'Renal and Urinary System',
                    'Endocrine', 'Hematology', 'Infectious Diseases', 'Reproductive System', 'Pediatrics', 'Psychiatry',
                    'Pharmacology', 'Musculoskeletal System'}
ANESTHESIA_SECTIONS = {'Clinical Anesthesia', 'Anesthesia Physics and Equipment', 'Regional Anesthesia', 'Cardiac Anesthesia',
                       'Thoracic Anesthesia', 'Pediatric Anesthesia', 'Orthopedic and Trauma Anesthesia', 'Pharmacology',
                       'Physiology', 'Anatomy', 'Respiratory System', 'Cardiovascular System', 'Fluids and Electrolytes',
                       'Emergency Medicine', 'Pain Management'}
BASIC_STUDENT_SECTIONS = {'General Chemistry', 'General Physics', 'General Biology', 'Anatomy', 'Physiology',
                          'Biochemistry', 'Pharmacology', 'Pathology', 'Microbiology', 'Genetics', 'Medical Terminology'}
NURSING_ONLY = {'Arterial Blood Gases and Acid-Base Balance', 'CPR and Chest Tube', 'ECG Interpretation and Arrhythmia',
                'IV Fluids', 'Surgical and Post-Operative Care', 'Pediatric Congenital Anomalies',
                'Nervous System and Special Senses', 'Multisystem', 'Prenatal Care', 'Physical Assessment',
                'Quality and Safety', 'Nursing Management', 'Fundamentals of Nursing'}
DENTAL_ONLY = {'Dental Basic Sciences', 'Oral Biology and Pathology', 'Clinical Dentistry',
               'Diagnosis and Non-Surgical Therapy', 'Allergic, Metabolic and Infection-Related Emergencies'}
ANESTHESIA_ONLY = {'Anesthesia Physics and Equipment', 'Regional Anesthesia', 'Cardiac Anesthesia', 'Thoracic Anesthesia',
                   'Pediatric Anesthesia', 'Orthopedic and Trauma Anesthesia'}
NOT_FOR_MEDICINE = NURSING_ONLY | DENTAL_ONLY | ANESTHESIA_ONLY | {
    'Aptitude (IQ)', 'General Chemistry', 'General Physics', 'General Biology', 'Medical Terminology'}

# Section when nothing matched, by subject (level-3) or sub-category name.
DEFAULT_SECTION = [
    (r'aptitude|iq', 'Aptitude (IQ)'), (r'chemistry', 'General Chemistry'), (r'physics', 'General Physics'),
    (r'biology', 'General Biology'), (r'terminology', 'Medical Terminology'), (r'anatomy', 'Anatomy'),
    (r'histology|cell biology', 'General Biology'), (r'physiology', 'Physiology'), (r'biochem', 'Biochemistry'),
    (r'pharmacol', 'Pharmacology'), (r'patholog', 'Pathology'), (r'microbio', 'Microbiology'), (r'ethic', 'Medical Ethics and Law'),
    (r'oral pathology|oral medicine', 'Oral Biology and Pathology'), (r'emergenc', 'Allergic, Metabolic and Infection-Related Emergencies'),
    (r'dent|endodont|prosthodont|periodont|oral|orthodont|pedodont', 'Clinical Dentistry'),
    (r'anesth', 'Clinical Anesthesia'), (r'nurs|management and leadership', 'Fundamentals of Nursing'),
    (r'pediat', 'Pediatrics'), (r'obstet|gyn', 'Reproductive System'), (r'urolog', 'Urology'), (r'surg', 'General Surgery'),
    (r'neuro', 'Neurology'), (r'ophthal', 'Ophthalmology'), (r'\bent\b', 'ENT (Otorhinolaryngology)'), (r'dermat', 'Dermatology'),
    (r'ortho', 'Musculoskeletal System'), (r'psych', 'Psychiatry'), (r'forensic', 'Forensic Medicine and Toxicology'),
    (r'radiolog', 'Radiology & Nuclear Medicine'), (r'family|community', 'Family Medicine'), (r'basic', 'Physiology'),
    (r'internal|medicine|step', 'Internal Medicine'),
]


def _compile(words):
    return re.compile(rf'(?<![a-z])(?:{words})', re.I)


def _name_words(name):
    words = re.sub(r'\(.*?\)|&|,|\band\b|\bof\b|\bthe\b|\bin\b', ' ', name.lower())
    words = re.sub(r'\b(diseases?|disorders?|infections?|conditions?|syndrome|system|management)\b', ' ', words)
    words = [w for w in words.split() if len(w) > 3]
    return '|'.join(re.escape(w[:-1] if w.endswith('s') else w) for w in words)


TOPIC_SECTION = {t: s for s, topics in SECTIONS.items() for t in topics}
TOPIC_RE = {}
for _topic in TOPIC_SECTION:
    parts = [p for p in (TOPIC_WORDS.get(_topic), re.escape(_topic.lower())) if p]
    TOPIC_RE[_topic] = _compile('|'.join(parts))
SECTION_RE = {s: _compile(w) for s, w in SECTION_WORDS.items() if s in SECTIONS}
PEDIATRIC_RE = re.compile(r'(?<![a-z])(newborn|neonat|infant|toddler|child|children|boy|girl|\d+[- ](day|week|month)s?[- ]old)', re.I)
AGE_RE = re.compile(r'(\d+)[- ]year[- ]old', re.I)


def plain(*parts):
    text = ' '.join(p or '' for p in parts)
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', html.unescape(text)).lower()


def field_of(path):
    joined = ' '.join(path).lower()
    if 'dentist' in joined or 'أسنان' in joined:
        return 'dental'
    if 'nurs' in joined or 'تمريض' in joined:
        return 'nursing'
    if 'anesthesia' in joined:
        return 'anesthesia'
    if path and path[0] == 'Medical Students' and len(path) > 1 and path[1] == 'Basic':
        return 'basic'
    return 'medicine'


def allowed_sections(field, path=()):
    if any('aptitude' in (p or '').lower() for p in path):
        return {'Aptitude (IQ)'}
    if field == 'dental':
        return DENTAL_SECTIONS
    if field == 'nursing':
        return NURSING_SECTIONS
    if field == 'anesthesia':
        return ANESTHESIA_SECTIONS
    if field == 'basic':
        return BASIC_STUDENT_SECTIONS
    return set(SECTIONS) - NOT_FOR_MEDICINE


def is_pediatric(text):
    if PEDIATRIC_RE.search(text):
        ages = [int(a) for a in AGE_RE.findall(text)]
        return not ages or min(ages) < 16
    ages = [int(a) for a in AGE_RE.findall(text)]
    return bool(ages) and min(ages) < 16


def _score(rx, question, extra):
    return 3 * len(rx.findall(question)) + len(rx.findall(extra))


def classify(question, extra, path):
    """-> (section, topic or None). `question` is the stem, `extra` the options and explanation (weighed less);
    path = [root, sub, subject or '']."""
    field = field_of(path)
    allowed = allowed_sections(field, path)
    best_topic, best_score = None, 0
    for topic, rx in TOPIC_RE.items():
        if TOPIC_SECTION[topic] not in allowed:
            continue
        score = _score(rx, question, extra)
        if score > best_score:
            best_topic, best_score = topic, score
    if best_topic:
        return TOPIC_SECTION[best_topic], best_topic
    best_section, best_score = None, 0
    for section, rx in SECTION_RE.items():
        if section not in allowed:
            continue
        score = _score(rx, question, extra)
        if score > best_score:
            best_section, best_score = section, score
    if best_section:
        return best_section, None
    hint = ' '.join(path[::-1]).lower()
    for pattern, section in DEFAULT_SECTION:
        if re.search(pattern, hint) and section in allowed:
            return section, None
    return ('Clinical Dentistry' if field == 'dental' else 'Fundamentals of Nursing' if field == 'nursing'
            else 'Clinical Anesthesia' if field == 'anesthesia' else 'Internal Medicine'), None


# ------------------------------------------------------------------ subject (level 3) when missing
SURGICAL_SECTIONS = {'General Surgery', 'Thoracic Surgery', 'Pediatric Surgery', 'Plastic Surgery', 'Musculoskeletal System', 'Urology'}
BASIC_SECTIONS = {'Biochemistry', 'Physiology', 'Anatomy', 'Genetics', 'Pharmacology', 'Microbiology', 'Pathology',
                  'General Chemistry', 'General Biology', 'General Physics', 'Medical Terminology'}
CLINICAL_SECTION_SUBJECT = {
    'Neurology': 'Neurology', 'Ophthalmology': 'Ophthalmology', 'ENT (Otorhinolaryngology)': 'ENT', 'Dermatology': 'Dermatology',
    'Musculoskeletal System': 'Orthopedics', 'Psychiatry': 'Psychiatry', 'Radiology & Nuclear Medicine': 'Radiology',
    'Forensic Medicine and Toxicology': 'Forensic Medicine & Toxicology', 'Clinical Anesthesia': 'Anesthesia',
    'Family Medicine': 'Family & Community Medicine', 'Public Health': 'Family & Community Medicine',
}
NURSING_SUBJECT_WORDS = [
    ('Maternity and Pediatric Nursing', r'pregnan|labou?r|postpartum|newborn|neonat|infant|child|breast|fetal|antenatal'),
    ('Critical Care Nursing', r'\bicu\b|ventilat|shock|\babg\b|intubat|cardiac arrest|\bcpr\b|critical'),
    ('Psychiatric and Community Nursing', r'psychiat|depress|schizo|anxiety|suicid|communit|home visit|epidemiolog'),
    ('Management and Leadership', r'delegat|leader|manager|prioriti|charge nurse|assignment|conflict'),
    ('Fundamentals of Nursing', r'hand hygiene|vital sign|bed bath|position|documentation|nursing process'),
]


def pick_subject(text, section, choices):
    """Choose one of `choices` (the level-3 names under the question's sub-category)."""
    if not choices:
        return None
    names = set(choices)
    if 'Medical Surgical Nursing' in names:
        for subject, words in NURSING_SUBJECT_WORDS:
            if subject in names and re.search(words, text):
                return subject
        return 'Medical Surgical Nursing'
    if 'General Chemistry' in names:  # Medical Students > Basic
        for pattern, subject in ((r'chem', 'General Chemistry'), (r'physics', 'General Physics'), (r'biology', 'General Biology'),
                                 (r'anatomy', 'General Anatomy'), (r'physiology', 'General Physiology'), (r'biochem', 'Biochemistry'),
                                 (r'pharmacol', 'General Pharmacology'), (r'patholog', 'General Pathology'),
                                 (r'terminology', 'Medical Terminology')):
            if re.search(pattern, section.lower()):
                return subject
        return 'General Biology'
    if section in CLINICAL_SECTION_SUBJECT and CLINICAL_SECTION_SUBJECT[section] in names:
        return CLINICAL_SECTION_SUBJECT[section]
    if section == 'Psychiatry' and 'Psychiatry' in names:
        return 'Psychiatry'
    gyn = 'Obstetrics and Gynecology'
    if section in ('Reproductive System',) and gyn in names and not re.search(r'testic|scrot|prostat', text):
        return gyn
    peds = 'Pediatrics'
    if peds in names and (section in ('Pediatrics', 'Growth and Development', 'Vaccination', 'Pediatric Surgery') or is_pediatric(text)):
        return peds
    surgery = 'Surgery' if 'Surgery' in names else 'General Surgery' if 'General Surgery' in names else None
    if surgery and (section in SURGICAL_SECTIONS or re.search(r'surg|operat|incision|laparo', text)):
        return surgery
    if 'Basic Sciences' in names and section in BASIC_SECTIONS:
        return 'Basic Sciences'
    return 'Internal Medicine' if 'Internal Medicine' in names else sorted(names)[0]
