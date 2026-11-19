# 세계 최고 학술 논문 작성을 위한 교통신호 규범집 (World-Class Paper Traffic Rules)

**문서 코드**: `RULE-WCP-2026-V1`  
**관리 주체**: 블루팀 시스템스 그룹 (HINAGI Systems Group)  
**적용 대상**: `Paper/` 하위의 모든 논문 원고(`.tex`, `.md`, `.pdf`)  
**제정 목적**: 1인/독립 연구자로서 세계 최고 권위 학술지(Nature, Science, JMLR, IEEE TPAMI) 및 탑티어 학술대회(NeurIPS, ICML) 최우수 논문상(Best Paper) 기준에 부합하는 무결점의 학술적 품격과 과학적 엄밀성을 항구적으로 유지하고 상호 교차 검증하기 위함.

---

## 1. 기본 철학 (The Solo Masterpiece Principle)

거대 AI 연구소의 물량 공세에 맞서는 독립 연구자의 유일한 무기는 **"날카로운 개념적 우아함(Sharp conceptual elegance), 빈틈없는 실증적 설계(Airtight empirical design), 그리고 냉철한 반증 가능성(Falsifiability)"**이다. 

세계 최고의 학술 논문은 연구의 실패와 한계를 숨기지 않으며, 행정적 요식행위에 기대지 않고, 데이터와 논리로 스스로 증명한다. 본 규범집은 논문 작성 시 반드시 준수해야 하는 **교통신호(적색·황색·녹색)** 체계를 정의한다.

---

## 2. 교통신호 3단계 분류 체계

```
🔴 RED LIGHT (적색 신호) : 즉시 반려 (Fatal Violation)
   - 적발 즉시 컴파일 중단 및 원고에서 완전 삭제. 예외 없음.

🟡 YELLOW LIGHT (황색 신호) : 엄격 통제 (Proceed with Scrutiny)
   - 구체적인 실험 데이터와 한계 명시가 수반되지 않으면 서술 불가.

🟢 GREEN LIGHT (녹색 신호) : 골든 스탠다드 (Mandatory Best Practice)
   - 세계 최고 학술 논문이 되기 위해 반드시 갖추어야 할 필수 규범.
```

---

## 3. 세부 10대 교통신호 규범 (The 10 Traffic Signals)

### 🔴 제1조: 행정적 요식행위 및 체크리스트 퇴출 (No Bureaucratic Boilerplate)
* **적색 금지**: 학술대회 투고 시 임시로 요구되는 행정 설문조사, 안내문, Q&A 문답식 체크리스트를 최종 논문 본문에 수록하는 행위.
  * *금지 예시*: `\section*{NeurIPS Paper Checklist}`, `Did you discuss limitations? [Yes]`, `Did you specify compute resources? [Yes]` 등.
* **학술 규범**: 최고의 논문은 체크리스트의 질문에 수동적으로 답변하지 않는다. 그 질문이 요구하는 학술적 본질(한계, 재현성, 컴퓨트 스펙, 윤리적 영향)을 논문 본문의 **정규 섹션(Methodology, Experimental Setup, Limitations and Threats to Validity)** 속에 유기적이고 품격 있는 학술 언어로 완전히 녹여내야 한다.

### 🔴 제2조: 과장 어휘 및 자기 찬양 금지 (No Promotional Hyperbole)
* **적색 금지**: 객관적 입증이 불가능한 홍보성·마케팅성 미사여구 사용.
  * *금지 단어*: `groundbreaking`, `revolutionary`, `game-changing`, `miraculous`, `flawless`, `unprecedented`, `astonishing`, `first ever in human history` 등.
* **학술 규범**: 감정적 형용사를 전면 배제하고, 구체적인 수치와 대조군으로만 진술한다.
  * *올바른 예시*: *"Our hybrid system improves action efficiency by 2.45x over unguided exploration"* (수치로 증명).

### 🔴 제3조: 벤치마크 및 데이터 출처 혼동 금지 (Strict Provenance Separation)
* **적색 금지**: 로컬 공개 25게임 스모크 점수(V6: 49.84, V10: 70.94)를 공식 히든 테스트 리더보드 점수(V6: 33.38, V10: 8.03)인 것처럼 혼용하거나 동일 선상에서 단순 비교하는 행위.
* **적색 금지**: 마감 이후 완료된 실행(V13: 23.41, `Succeeded (after deadline)`)을 공식 대회 마감 내 점수처럼 호도하는 행위.
* **학술 규범**: "Official Competition Leaderboard (Hidden 110 Games)"와 "Local Public Smoke Suite (25 Known Games)"를 명확히 별개의 라벨과 테이블로 분리 표기해야 한다.

### 🔴 제4조: 미통합 연구 모듈의 실전 혼입 금지 (No Phantom Systems)
* **적색 금지**: 연구 브랜치나 독립 프로토타입에서만 실험된 기법(예: Held-Karp, Gauge-fixed Sokoban, RVICS, Swarm Coordinator)을 33.38점을 획득한 V6 공식 제출물이나 V13 생산 후보의 통합 기능으로 서술하는 행위.
* **학술 규범**: 실전 제출 아티팩트(V6 notebook hash `bb532e...`)에 포함된 기능만 메인 아키텍처로 서술하고, 미통합 실험 모듈은 "Follow-up Research Prototypes (Research-Only)" 섹션으로 엄격히 격리한다.

### 🔴 제5조: 사이비 정리 및 비약적 증명 금지 (No Pseudo-Theorems)
* **적색 금지**: 현실적인 전제조건(에이전트 모델의 무결성, 상태 파싱의 완벽성 등)이 증명되지 않은 공학적 휴리스틱을 수학적 `Theorem`이나 `Proof`로 포장하는 행위.
  * *금지 예시*: $A_{\text{AI}} \le A_{\text{human}} + 2D_{\text{mec}}$와 같은 미증명 부등식을 보편 정리(Universal Theorem)로 주장하는 행위.
* **학술 규범**: 엄밀한 수학적 증명이 갖추어지지 않은 경우 `Analytical Estimate`, `Conditional Engineering Bound`, 또는 `Working Hypothesis`로 정확히 격하하여 기술한다.

---

### 🟡 제6조: 결합적 퇴행의 정직한 진술 (Confounded Causality Audit)
* **황색 주의**: 다수의 하이퍼파라미터가 동시에 변경되었을 때, 특정 단일 요인이 전체 점수 하락의 단독 원인이라고 단정하는 행위.
  * *주의 사례*: V6 $\to$ V10에서 히스토리(150 $\to$ 36), 컨텍스트(128K $\to$ 56K), 드레인(58K $\to$ 16K), 툴 스텝(0 $\to$ 12), 양자 핸드오버가 동시에 바뀌었음에도 "150 $\to$ 36턴 변경이 25.35점 하락의 전체 원인이다"라고 단정하는 서술.
* **학술 규범**: 통제된 단일 변수 실험(예: `vc33` 대조군)으로 입증된 사실과, 다중 변수 결합으로 인해 인과관계가 분리되지 않은 후보 가설(Candidate Hypotheses)을 명확히 구분하여 서술한다.

### 🟡 제7조: 원격 텔레메트리와 모델 추정치의 구분 (Direct Telemetry vs Model Estimates)
* **황색 주의**: 수식으로 계산된 기대값이나 모델 추정치(예: Radix Cache 98.5% 적중률)를 실제 GPU 서버에서 물리적으로 측정한 로그 텔레메트리인 것처럼 표현하는 행위.
* **학술 규범**: 실측 데이터는 `Measured server telemetry`로, 유도된 이론치는 `Analytically derived estimate under assumption X`로 명시한다.

---

### 🟢 제8조: 60초 심사를 돌파하는 1등급 벡터 그래픽 (First-Class Visuals)
* **녹색 필수**: 심사위원은 논문을 열고 60초 이내에 다이어그램과 도표를 보고 논문의 격을 판단한다.
* **학술 규범**:
  1. 흐릿한 래스터 이미지(저해상도 PNG/JPG 캡처) 본문 삽입 금지. 모든 아키텍처 다이어그램과 플롯은 **LaTeX TikZ** 또는 **무한 해상도 벡터 PDF**로 렌더링되어야 한다.
  2. 모든 그림과 표는 **본문을 읽지 않고 캡션만 읽어도 완전히 이해될 수 있도록(Self-Contained Caption)** 상세한 설명과 범례를 포함해야 한다.

### 🟢 제9조: 선제적 자기 비판과 실패의 학술화 (Pre-emptive Limitations)
* **녹색 필수**: 최고의 연구자는 자신의 한계를 심사위원이 지적하기 전에 스스로 가장 냉철하게 폭로한다.
* **학술 규범**:
  1. 독립된 섹션(`Limitations and Threats to Validity`)을 반드시 전진 배치한다.
  2. 실패한 버전(V9의 세그먼트 충돌, V10의 대형 회귀, V11/V12의 프로브 실패)을 감추지 않고, 왜 실패했는지를 파헤쳐 커뮤니티에 기여하는 **"독보적인 반면교사(Negative Results as First-Class Science)"**로 승화시킨다.

### 🟢 제10조: 완전한 재현성 및 버전 원장 동기화 (Absolute Reproducibility)
* **녹색 필수**: 모든 논문 버전은 고유 해시와 함께 원장에 동결되며, 언제든 단일 명령어로 재현 빌드되어야 한다.
* **학술 규범**:
  1. 인용된 모든 핵심 결과는 검증 가능한 커밋 해시, 노트북 아티팩트 SHA-256, 공식 Submission ID에 1:1로 매핑되어야 한다.
  2. 시스템 독립성을 위해 `\IfFontExistsTF` 등을 적용하여 어떤 표준 TeX 컴파일 환경에서도 빌드 실패가 없어야 한다.

---

## 4. 논문 버전별 교통신호 자동 점검표 (Traffic Signals Audit Protocol)

논문 원고(`.tex`)가 생성되거나 수정될 때마다 다음 7개 체크포인트를 자동으로 검증한다:

```
[교통신호 점검 체크리스트]
[ ] 1. (RED)    행정 체크리스트 문답 블록(NeurIPS Checklist 등)이 완전히 제거되었는가?
[ ] 2. (RED)    과장 어휘(groundbreaking, revolutionary, flawless 등)가 전무한가?
[ ] 3. (RED)    로컬 스모크 점수와 공식 히든 테스트 점수가 엄격히 분리 표기되었는가?
[ ] 4. (RED)    V13이나 미통합 연구 모듈(Held-Karp, RVICS 등)에 허위 통합 주장이 없는가?
[ ] 5. (RED)    증명되지 않은 휴리스틱이 Theorem/Proof로 둔갑하지 않았는가?
[ ] 6. (YELLOW) V6->V10 회귀 원인이 결합적 가설로 정직하게 다루어졌는가?
[ ] 7. (GREEN)  모든 그림/표가 고해상도 벡터 그래픽이며 캡션이 자족적인가?
```

모든 항목이 통과(`PASS`)되어야만 `PAPER_VERSION_LEDGER.md`에 공식 빌드로 승인 등록된다.

