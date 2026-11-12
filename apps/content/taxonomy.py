"""
The platform's exam taxonomy, rebuilt from the old platform's export (categories_flat_clean.xlsx)
and the questions that actually use it.

  Category (level 1) -> Sub Category (level 2) -> Sub Sub-Category (level 3)
  Section: shared by all exams (no category); only sections that have questions on the
           path the student picked appear in the exam builder.
  Topic:   belongs to one section; shown only as an optional filter inside its section.

Loaded with `python manage.py seed_taxonomy` (idempotent). `--prune` also removes categories that
are not in this tree, but only when nothing (question, package, exam) is linked to them.
Cleanup applied to the export: study years (4th/5th/6th Year) and universities removed, their
questions moved to the matching subject; exam-year groups (2024 Exam, 2026 Exam, RMS - 2024 Exams)
removed, their questions moved to the matching subject; duplicate spellings merged.
"""

MEDICINE = ['Internal Medicine', 'Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Basic Sciences']
DENTAL = [
    'Conservative & Operative Dentistry', 'Endodontics', 'Prosthodontics', 'Oral Surgery & Anesthesia',
    'Oral Pathology & Medicine', 'Oral Radiology', 'Pediatric Dentistry', 'Periodontics', 'Pharmacology',
    'Dental Emergencies', 'Microbiology',
]
NURSING = [
    'Medical Surgical Nursing', 'Maternity and Pediatric Nursing', 'Critical Care Nursing',
    'Psychiatric and Community Nursing', 'Management and Leadership', 'Fundamentals of Nursing',
]
PARTS = ['Part 1', 'Part 2']
BOARD_SPECIALTIES = [
    'Internal Medicine', 'General Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Ophthalmology', 'ENT',
    'Radiology', 'Forensic Medicine', 'Orthopedic Surgery', 'Dermatology', 'Neurosurgery', 'Urology',
    'Psychiatry', 'Anesthesia', 'Accident and Emergency Medicine', 'Family Medicine', 'Nuclear Medicine',
    'Pathology', 'Clinical Laboratory Microbiology', 'Physical Medicine and Rehabilitation',
]

# (level-1 name, [(level-2 name, [level-3 names])]). Level-1 names match the rows already entered by hand.
TREE = [
    ('Medical Students', [
        ('Basic', [
            'General Biology', 'General Chemistry', 'General Physics', 'General Anatomy', 'Cell Biology & Histology',
            'General Physiology', 'Biochemistry', 'General Pharmacology', 'General Pathology', 'Medical Terminology',
        ]),
        ('Clinical', [
            'Internal Medicine', 'General Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Neurology',
            'Ophthalmology', 'ENT', 'Dermatology', 'Orthopedics', 'Anesthesia', 'Forensic Medicine & Toxicology',
            'Psychiatry', 'Radiology', 'Family & Community Medicine',
        ]),
    ]),
    ('JMC - الفحص الإجمالي - امتياز', [
        ('JMC - طب بشري', MEDICINE),
    ]),
    ('Residency Entrance - Medicine', [
        ('Royal Medical Services (RMS)', MEDICINE),
        ('Jordan University Hospital (JUH)', MEDICINE),
        ('King Abdullah University Hospital (KAUH)', MEDICINE),
        ('King Hussein Cancer Center (KHCC)', MEDICINE),
        ('Private Hospitals (PH)', MEDICINE),
        ('MOH وزارة الصحة (التنافسي - الإعلان المفتوح)', MEDICINE + ['Aptitude (IQ) - أسئلة القدرات']),
    ]),
    ('Residency and Board Exams', [(name, PARTS) for name in BOARD_SPECIALTIES]),
    ('SMLE - Prometric', [
        ('SMLE - Medicine', MEDICINE + ['Psychiatry', 'Ethics']),
        ('SMLE - Nursing', NURSING[:5]),
    ]),
    ('Dentistry', [
        ('Residency Entrance - Dentistry', DENTAL),
        ('MOH وزارة الصحة (التنافسي - دخول الإقامة)', DENTAL),
        ('Royal Medical Services (RMS) - Dentistry', DENTAL),
        ('Residency and Board Exams - Dentistry', DENTAL),
        ('JMC - طب أسنان', DENTAL),
    ]),
    ('Nursing', [
        ('امتحان مزاولة المهنة للتمريض', NURSING),
    ]),
    ('Pharmacy', [
        ("Bachelor's", [
            'Pharmacology & Pharmacotherapeutics', 'Pharmaceutics & Dosage Forms', 'Pharmaceutical Chemistry',
            'Clinical Pharmacy & Pharmacokinetics', 'Trade Names & Local Market', 'Law & Ethics',
            'Pharmacoeconomics & Biostatistics', 'Patient Counseling',
        ]),
    ]),
    ('UWORLD', [
        ('Step 2', ['Internal Medicine', 'Surgery', 'Pediatrics', 'Obstetrics and Gynecology', 'Psychiatry', 'Miscellaneous']),
    ]),
    ('USMLE Highly Suggested Questions', [
        ('USMLE', ['Step 1', 'Step 2 CK']),
    ]),
    ('MRCP', [
        ('MRCP Part 1', ['Cardiology']),
    ]),
]

# Level-1 rows renamed earlier (by hand or by the first version of this seed): renamed back in
# place, so whatever is linked to them stays linked.
ROOT_RENAMES = {
    'SMLE- prometric': 'SMLE - Prometric',
    'Residency and Board exams': 'Residency and Board Exams',
    'Residency and Board Exams - البورد والإقامة': 'Residency and Board Exams',
    'Residency Entrance - امتحانات دخول الإقامة': 'Residency Entrance - Medicine',
    'USMLE highly suggested questions': 'USMLE Highly Suggested Questions',
    'USMLE': 'USMLE Highly Suggested Questions',
    'MRCP (UK)': 'MRCP',
    'JMC - الفحص الإجمالي': 'JMC - الفحص الإجمالي - امتياز',
}

# Level-1 rows that --prune leaves alone even though they are not in TREE (decision pending).
PRUNE_KEEP = {'Free Trial (20 questions)'}

# Section -> its topics. Section names are unique; a topic name appears under one section only.
SECTIONS = {
    # Clinical systems
    'Respiratory System': [
        'Obstructive Lung Disease', 'Restrictive Lung Disease', 'Interstitial Lung Disease', 'Lung Neoplasms',
        'Pulmonary Vasculature Disease', 'Pulmonary Embolism', 'Pulmonary Edema', 'Pleural Diseases',
        'Pleural Effusion', 'Pneumothorax', 'Occupational Lung Diseases', 'Pneumonia',
        'Upper Respiratory Tract Infections', 'Lower Respiratory Tract Infections',
        'Neonatal Respiratory Conditions', 'Sleep Disorders',
    ],
    'Cardiovascular System': [
        'Ischemic Heart Disease', 'Acute Coronary Syndrome', 'Myocardial Infarction', 'Congestive Heart Failure',
        'Arrhythmias & ECG', 'Cardiomyopathies', 'Hypertrophic Cardiomyopathy', 'Pericardial Disease',
        'Valvular Heart Disease', 'Congenital Heart Disease', 'Arterial Diseases & Hypertension', 'Venous Diseases',
    ],
    'Gastrointestinal System': [
        'Esophageal Diseases', 'Stomach Diseases', 'Peptic Ulcer', 'Duodenal Ulcer', 'Gastric Cancer',
        'Small Intestine Diseases', 'Colon Diseases', 'Inflammatory Bowel Disease', 'Diverticulitis',
        'Diverticular Disease & Angiodysplasia', 'Rectal Disease', 'Perianal Diseases', 'Appendix Diseases',
        'Bowel Obstruction and Perforation', 'Functional Gastrointestinal Disorders', 'GI Bleeding',
        'Liver Diseases', 'Jaundice', 'Gallbladder Diseases', 'Pancreas Diseases', 'Salivary Gland Diseases',
    ],
    'Renal and Urinary System': [
        'Renal Failure', 'Proteinuria & Hematuria', 'Glomerular Disease', 'Nephrotic Syndrome',
        'Tubulointerstitial Disease', 'Renal Cystic Disease', 'Renal-Vascular Disease',
        'Renal Stones & Obstruction', 'Renal Neoplasms', 'Renal Infections', 'Bladder Diseases', 'Prostate Disease',
    ],
    'Fluids and Electrolytes': ['Electrolyte Disorders', 'Acid-Base Disorders', 'Fluid Replacement'],
    'Hematology': [
        'Anticoagulation', 'Platelets & Coagulopathies', 'Myeloproliferative Diseases', 'Plasma Cell Disorders',
        'Hodgkin Lymphoma', 'Non-Hodgkin Lymphoma', 'Spleen Diseases', 'Hyposplenism', 'Blood Transfusion',
        'Chemotherapy',
    ],
    'Endocrine': [
        'Thyroid Diseases', 'Hyperthyroidism', 'Graves Disease', 'Parathyroid Diseases', 'Pituitary Diseases',
        'Adrenal Diseases', 'Bone Disorders', 'Metabolic Disorders', 'Nutritional Disorders',
    ],
    'Rheumatology': [
        'Connective Tissue Diseases', 'Crystal-Induced Arthritis', 'Vasculitis', 'Osteoarthritis',
        'Rheumatoid Arthritis', 'Infectious Arthritis', 'Autoimmune Diseases', 'Granulomatous Diseases',
    ],
    'Immunology': ['Immunodeficiency Disorders', 'Allergic Reactions'],
    'Neurology': [
        'Movement Disorders', 'Altered Mental Status', 'Demyelinating Disease', 'Neuromuscular Disease',
        'Spinal Cord Diseases', 'Seizures', 'Meningitis & Encephalitis', 'Brain Tumor', 'Brain Hemorrhage',
        'Head Trauma', 'Basal Skull Fracture', 'Brain Death', 'Neural Tube Defects', 'Acute Flaccid Paralysis',
        'Infantile Hypotonia',
    ],
    'Infectious Diseases': [
        'Bacterial Infections', 'Viral Infections', 'Fungal Infections', 'Parasitic Infections',
        'Zoonotic Diseases', 'Sepsis', 'Septic Shock', 'Fever', 'HIV',
        'Sexually Transmitted Diseases (STD)', 'GI Infections', 'Genitourinary Infections',
        'Respiratory Infections', 'Ear Infections',
    ],
    'Reproductive System': [
        'Antenatal Care', 'Physiological Changes in Pregnancy', 'Pregnancy & Labor', 'Assisted Vaginal Delivery',
        'Ectopic Pregnancy', 'Antepartum Hemorrhage', 'Postpartum Hemorrhage',
        'Hypertensive Disorders of Pregnancy', 'Gestational Trophoblastic Neoplasia', 'Puerperium',
        'Multiple Pregnancy', 'Placental Disorders', 'Oligohydramnios and Polyhydramnios', 'Rh Incompatibility',
        'Drugs in Pregnancy', 'Pelvic Inflammatory Disease', 'Urinary Incontinence', 'Genital Prolapse',
        'Uterine Fibroid', 'Endometriosis', 'Infertility', 'Amenorrhea', 'Abnormal Uterine Bleeding',
        'Menorrhagia', 'Menopause', 'Polycystic Ovary Syndrome (PCOS)', 'Ovarian Disorders', 'Ovarian Cancer',
        'Endometrial Cancer', 'Cervical Cancer', 'Contraception', 'Testicular Diseases', 'Genital Disorders',
        'Embryology',
    ],
    'General Surgery': [
        'Pre- and Post-Operative Management', 'Abdominal Trauma', 'Hernia', 'Breast Diseases',
        'Wounds, Ulcers & Cysts', 'Bariatric Surgery', 'Vascular Surgery',
    ],
    'Thoracic Surgery': ['Chest Trauma'],
    'Pediatric Surgery': ['Intussusception', 'Congenital GI Defects'],
    'Plastic Surgery': [],
    'Pediatrics': ['Neonatology', 'Congenital Conditions'],
    'Growth and Development': ['Disorders of Growth', 'Developmental Assessment'],
    'Vaccination': ['Vaccines'],
    'Genetics': ['Genetic Disorders'],
    'Musculoskeletal System': ['Orthopedic Fractures', 'Orthopedic Tumors', 'Bone and Joint Disorders'],
    'Dermatology': ['Dermatitis', 'Skin Lesions', 'Skin Cancer'],
    'Psychiatry': ['Depression'],
    'Ophthalmology': ['Eye Infections'],
    'Pharmacology': ['Drug-Induced Diseases', 'Adverse Drug Reactions', 'Immunosuppressants (Cyclosporine)'],
    'Forensic Medicine and Toxicology': ['Poisoning'],
    'Emergency Medicine': [],
    'Family Medicine': [],
    'Public Health': [],
    'Radiology & Nuclear Medicine': [],
    'Biochemistry': [],
    'Internal Medicine': [],
    # Anesthesia (residency)
    'Anesthesia Physics and Equipment': [],
    'Clinical Anesthesia': ['IV Anesthesia', 'Obstetric Anesthesia', 'Liver Physiology in Anesthesia'],
    'Regional Anesthesia': ['Local Anesthesia'],
    'Cardiac Anesthesia': [],
    'Thoracic Anesthesia': [],
    'Pediatric Anesthesia': [],
    'Orthopedic and Trauma Anesthesia': [],
    # Dentistry
    'Dental Basic Sciences': [
        'Gross Anatomy', 'Head and Neck Anatomy', 'General Physiology', 'Oral Physiology', 'Cardiac Physiology',
        'Renal Physiology', 'Respiratory Physiology', 'Endocrine Physiology', 'Neurophysiology',
        'Dental Biochemistry', 'Vitamins', 'Oral Microbiology', 'Dental Pharmacology',
    ],
    'Oral Biology and Pathology': [
        'Dental Anatomy and Oral Histology', 'Oral Embryology, Salivary Glands and TMJ', 'Oral Pathology',
        'Oral Neoplasms', 'Tissue Injury',
    ],
    'Clinical Dentistry': [
        'Dental Materials', 'Prosthodontics', 'Occlusion', 'Endodontic Surgery', 'Oral and Maxillofacial Surgery',
        'Dental Radiology', 'Infection Control', 'Periodontics',
    ],
    'Diagnosis and Non-Surgical Therapy': [],
    'Allergic, Metabolic and Infection-Related Emergencies': [],
    # Nursing
    'Arterial Blood Gases and Acid-Base Balance': [],
    'CPR and Chest Tube': [],
    'ECG Interpretation and Arrhythmia': [],
    'IV Fluids': [],
    'Surgical and Post-Operative Care': [],
    'Pediatric Congenital Anomalies': ['Cleft Lip and Palate', 'Spina Bifida', 'Hirschsprung Disease'],
    'Nervous System and Special Senses': [],
    'Multisystem': [],
    'Prenatal Care': [],
    'Physical Assessment': [],
    'Quality and Safety': [],
    'Nursing Management': [],
    # Basic sciences, aptitude, ethics, pharmacy and nursing
    'General Biology': ['Cell Biology', 'Molecular Biology', 'Ecology & Evolution', 'Plant & Animal Biology'],
    'General Chemistry': [
        'Stoichiometry', 'Chemical Bonding & Structure', 'Thermochemistry', 'Solutions & Equilibrium',
        'Chemical Nomenclature', 'Organic Chemistry',
    ],
    'General Physics': [],
    'Anatomy': ['Head and Neck', 'Thorax', 'Abdomen and Pelvis', 'Limbs', 'Neuroanatomy'],
    'Physiology': [],
    'Pathology': [],
    'Microbiology': [],
    'Medical Terminology': [],
    'Aptitude (IQ)': ['Verbal Reasoning', 'Numerical Reasoning', 'Logical Reasoning'],
    'Medical Ethics and Law': [],
    'ENT (Otorhinolaryngology)': [],
    'Urology': [],
    'Pharmacy Practice': [],
    'Fundamentals of Nursing': [],
    'Pain Management': [],
}
