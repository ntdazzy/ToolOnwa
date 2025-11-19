/**********************************************************************/
/* テーブル名    ：  ブランドマスタ
/* テーブルID    ：  M_BRAND
/* 作成日(作成者)：  2022/12/22（CUBE深川）
/* 更新          ：  
/**********************************************************************/
/*** テーブル作成部 ***/
/* テーブル削除 */
DROP TABLE  M_BRAND  CASCADE CONSTRAINTS PURGE;
/* エラーハンドリング */
--WHENEVER OSERROR  EXIT OSCODE      ROLLBACK
--WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK
/* テーブル作成 */
CREATE TABLE  M_BRAND
  (
    BRAND_CD                       VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランド  */
    YUKO_END_DT                    VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  有効終了日  */
    YUKO_STA_DT                    VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  有効開始日  */
    SEISAN_SOSI_CD                 VARCHAR2(10)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  生産品番組織コード  */
    BRAND_NM                       VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランド名称  */
    BRAND_KN_NM                    VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランドカナ名称  */
    SHOHIN_CATEGORY                VARCHAR2(4)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  商品カテゴリ  */
    MBRAND1_CD                     VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド1  */
    MBRAND1_NM                     VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド1名称  */
    MBRAND1_KN                     VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド1カナ名称  */
    MBRAND2_CD                     VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド2  */
    MBRAND2_NM                     VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド2名称  */
    MBRAND2_KN                     VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド2カナ名称  */
    MBRAND3_CD                     VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド3  */
    MBRAND3_NM                     VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド3名称  */
    MBRAND3_KN                     VARCHAR2(48)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  主ブランド3カナ名称  */
    BRAND_GRP1_CD                  VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランドグループ1  */
    BRAND_GRP2_CD                  VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランドグループ2  */
    BRAND_GRP3_CD                  VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランドグループ3  */
    BRAND_GRP4_CD                  VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランドグループ4  */
    BRAND_GRP5_CD                  VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランドグループ5  */
    RN_KB                          VARCHAR2(1)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  RN区分  */
    EXPOVRM_RT                     NUMBER(3,2)      DEFAULT  ON  NULL 0   NOT NULL,  /*  輸出間接費率(量産)  */
    EXPOVRS_RT                     NUMBER(3,2)      DEFAULT  ON  NULL 0   NOT NULL,  /*  輸出間接費率(サンプル)  */
    BRAND_Z_KB                     VARCHAR2(2)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ブランド属性区分  */
    SEI_STOP_KB                    VARCHAR2(1)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  生産中止区分  */
    SAP_CREATE_DT                  VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ登録日付  */
    SAP_CREATE_TM                  VARCHAR2(6)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ登録時刻  */
    SAP_CREATE_LTIMESTAMP          VARCHAR2(15)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ登録ローカルタイムスタンプ  */
    SAP_CREATE_USR_ID              VARCHAR2(12)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ登録ユーザID  */
    SAP_CREATE_PGM_ID              VARCHAR2(40)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ登録プログラム  */
    SAP_UPDATE_DT                  VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ変更日付  */
    SAP_UPDATE_TM                  VARCHAR2(6)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ変更時刻  */
    SAP_UPDATE_LTIMESTAMP          VARCHAR2(15)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ変更ローカルタイムスタンプ  */
    SAP_UPDATE_USR_ID              VARCHAR2(12)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ変更ユーザID  */
    SAP_UPDATE_PGM_ID              VARCHAR2(40)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ＳＡＰ変更プログラム  */
    aaAAA                          VARCHAR2(12)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  ?dasdasdasd  */
    CREATE_DT                      VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  登録日  */
    CREATE_TM                      VARCHAR2(6)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  登録時間  */
    CREATE_USR_ID                  VARCHAR2(10)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  登録ユーザーＩＤ  */
    CREATE_PGM_ID                  VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  登録プログラムＩＤ  */
    UPDATE_DT                      VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  更新日  */
    UPDATE_TM                      VARCHAR2(6)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  更新時間  */
    UPDATE_USR_ID                  VARCHAR2(10)     DEFAULT  ON  NULL ' ' NOT NULL,  /*  更新ユーザーＩＤ  */
    UPDATE_PGM_ID                  VARCHAR2(8)      DEFAULT  ON  NULL ' ' NOT NULL,  /*  更新プログラムＩＤ  */
    DEL_FG                         VARCHAR2(1)      DEFAULT  ON  NULL ' ' NOT NULL   /*  削除フラグ  */
  )
  PCTFREE 5
  PCTUSED 95
  TABLESPACE TBS_MU_TBL
LOGGING;
/* PRIMARY KEY制約の追加 */
ALTER TABLE  M_BRAND
  ADD CONSTRAINT  PK_M_BRAND PRIMARY KEY
  (
    BRAND_CD                        ,  /* ブランド */
    YUKO_END_DT                        /* 有効終了日 */
  ) USING INDEX
  PCTFREE 5
  TABLESPACE TBS_MU_IDX
;
/* PRIMARY KEY制約の使用禁止 */
--ALTER TABLE  M_BRAND  DISABLE CONSTRAINT  PK_M_BRAND ;
/*** コメント作成部 ***/
/* コメントの作成 */
COMMENT ON TABLE  M_BRAND                                   IS 'ブランドマスタ';
COMMENT ON COLUMN M_BRAND.BRAND_CD                                     IS 'ブランド';
COMMENT ON COLUMN M_BRAND.YUKO_END_DT                                  IS '有効終了日';
COMMENT ON COLUMN M_BRAND.YUKO_STA_DT                                  IS '有効開始日';
COMMENT ON COLUMN M_BRAND.SEISAN_SOSI_CD                               IS '生産品番組織コード';
COMMENT ON COLUMN M_BRAND.BRAND_NM                                     IS 'ブランド名称';
COMMENT ON COLUMN M_BRAND.BRAND_KN_NM                                  IS 'ブランドカナ名称';
COMMENT ON COLUMN M_BRAND.SHOHIN_CATEGORY                              IS '商品カテゴリ';
COMMENT ON COLUMN M_BRAND.MBRAND1_CD                                   IS '主ブランド1';
COMMENT ON COLUMN M_BRAND.MBRAND1_NM                                   IS '主ブランド1名称';
COMMENT ON COLUMN M_BRAND.MBRAND1_KN                                   IS '主ブランド1カナ名称';
COMMENT ON COLUMN M_BRAND.MBRAND2_CD                                   IS '主ブランド2';
COMMENT ON COLUMN M_BRAND.MBRAND2_NM                                   IS '主ブランド2名称';
COMMENT ON COLUMN M_BRAND.MBRAND2_KN                                   IS '主ブランド2カナ名称';
COMMENT ON COLUMN M_BRAND.MBRAND3_CD                                   IS '主ブランド3';
COMMENT ON COLUMN M_BRAND.MBRAND3_NM                                   IS '主ブランド3名称';
COMMENT ON COLUMN M_BRAND.MBRAND3_KN                                   IS '主ブランド3カナ名称';
COMMENT ON COLUMN M_BRAND.BRAND_GRP1_CD                                IS 'ブランドグループ1';
COMMENT ON COLUMN M_BRAND.BRAND_GRP2_CD                                IS 'ブランドグループ2';
COMMENT ON COLUMN M_BRAND.BRAND_GRP3_CD                                IS 'ブランドグループ3';
COMMENT ON COLUMN M_BRAND.BRAND_GRP4_CD                                IS 'ブランドグループ4';
COMMENT ON COLUMN M_BRAND.BRAND_GRP5_CD                                IS 'ブランドグループ5';
COMMENT ON COLUMN M_BRAND.RN_KB                                        IS 'RN区分';
COMMENT ON COLUMN M_BRAND.EXPOVRM_RT                                   IS '輸出間接費率(量産)';
COMMENT ON COLUMN M_BRAND.EXPOVRS_RT                                   IS '輸出間接費率(サンプル)';
COMMENT ON COLUMN M_BRAND.BRAND_Z_KB                                   IS 'ブランド属性区分';
COMMENT ON COLUMN M_BRAND.SEI_STOP_KB                                  IS '生産中止区分';
COMMENT ON COLUMN M_BRAND.SAP_CREATE_DT                                IS 'ＳＡＰ登録日付';
COMMENT ON COLUMN M_BRAND.SAP_CREATE_TM                                IS 'ＳＡＰ登録時刻';
COMMENT ON COLUMN M_BRAND.SAP_CREATE_LTIMESTAMP                        IS 'ＳＡＰ登録ローカルタイムスタンプ';
COMMENT ON COLUMN M_BRAND.SAP_CREATE_USR_ID                            IS 'ＳＡＰ登録ユーザID';
COMMENT ON COLUMN M_BRAND.SAP_CREATE_PGM_ID                            IS 'ＳＡＰ登録プログラム';
COMMENT ON COLUMN M_BRAND.SAP_UPDATE_DT                                IS 'ＳＡＰ変更日付';
COMMENT ON COLUMN M_BRAND.SAP_UPDATE_TM                                IS 'ＳＡＰ変更時刻';
COMMENT ON COLUMN M_BRAND.SAP_UPDATE_LTIMESTAMP                        IS 'ＳＡＰ変更ローカルタイムスタンプ';
COMMENT ON COLUMN M_BRAND.SAP_UPDATE_USR_ID                            IS 'ＳＡＰ変更ユーザID';
COMMENT ON COLUMN M_BRAND.SAP_UPDATE_PGM_ID                            IS 'ＳＡＰ変更プログラム';
COMMENT ON COLUMN M_BRAND.aaAAA                                        IS '?dasd';
COMMENT ON COLUMN M_BRAND.CREATE_DT                                    IS '登録日';
COMMENT ON COLUMN M_BRAND.CREATE_TM                                    IS '登録時間';
COMMENT ON COLUMN M_BRAND.CREATE_USR_ID                                IS '登録ユーザーＩＤ';
COMMENT ON COLUMN M_BRAND.CREATE_PGM_ID                                IS '登録プログラムＩＤ';
COMMENT ON COLUMN M_BRAND.UPDATE_DT                                    IS '更新日';
COMMENT ON COLUMN M_BRAND.UPDATE_TM                                    IS '更新時間';
COMMENT ON COLUMN M_BRAND.UPDATE_USR_ID                                IS '更新ユーザーＩＤ';
COMMENT ON COLUMN M_BRAND.UPDATE_PGM_ID                                IS '更新プログラムＩＤ';
COMMENT ON COLUMN M_BRAND.DEL_FG                                       IS '削除フラグ';
