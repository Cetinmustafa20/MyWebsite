CREATE TABLE TabletKayitlari (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    TabletId NVARCHAR(50) NOT NULL UNIQUE,
    MakineId INT NOT NULL REFERENCES Makineler(Id),
    TabletAdi NVARCHAR(100) NULL,
    SonAktivite DATETIME2 NULL,
    Aktif BIT NOT NULL DEFAULT 1,
    OlusturmaTarihi DATETIME2 NOT NULL DEFAULT GETDATE()
);

CREATE UNIQUE INDEX UX_TabletKayitlari_AktifMakine
ON TabletKayitlari(MakineId)
WHERE Aktif = 1;

CREATE TABLE OperatorMakineYetkileri (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    OperatorId INT NOT NULL REFERENCES Operatorler(Id),
    MakineId INT NOT NULL REFERENCES Makineler(Id),
    Aktif BIT NOT NULL DEFAULT 1,
    OlusturmaTarihi DATETIME2 NOT NULL DEFAULT GETDATE()
);

CREATE UNIQUE INDEX UX_OperatorMakineYetkileri
ON OperatorMakineYetkileri(OperatorId, MakineId);
