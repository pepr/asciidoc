<map version="freeplane 1.3.0">
<!--To view this file, download free mind mapping software Freeplane from http://freeplane.sourceforge.net -->
<node TEXT="AsciiDoc -- big picture" ID="ID_1723255651" CREATED="1283093380553" MODIFIED="1442487901439" MIN_WIDTH="2"><hook NAME="MapStyle">

<map_styles>
<stylenode LOCALIZED_TEXT="styles.root_node">
<stylenode LOCALIZED_TEXT="styles.predefined" POSITION="right">
<stylenode LOCALIZED_TEXT="default" MAX_WIDTH="600" COLOR="#000000" STYLE="as_parent">
<font NAME="SansSerif" SIZE="10" BOLD="false" ITALIC="false"/>
</stylenode>
<stylenode LOCALIZED_TEXT="defaultstyle.details"/>
<stylenode LOCALIZED_TEXT="defaultstyle.note"/>
<stylenode LOCALIZED_TEXT="defaultstyle.floating">
<edge STYLE="hide_edge"/>
<cloud COLOR="#f0f0f0" SHAPE="ROUND_RECT"/>
</stylenode>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.user-defined" POSITION="right">
<stylenode LOCALIZED_TEXT="styles.topic" COLOR="#18898b" STYLE="fork">
<font NAME="Liberation Sans" SIZE="10" BOLD="true"/>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.subtopic" COLOR="#cc3300" STYLE="fork">
<font NAME="Liberation Sans" SIZE="10" BOLD="true"/>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.subsubtopic" COLOR="#669900">
<font NAME="Liberation Sans" SIZE="10" BOLD="true"/>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.important">
<icon BUILTIN="yes"/>
</stylenode>
</stylenode>
<stylenode LOCALIZED_TEXT="styles.AutomaticLayout" POSITION="right">
<stylenode LOCALIZED_TEXT="AutomaticLayout.level.root" COLOR="#000000">
<font SIZE="18"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,1" COLOR="#0033ff">
<font SIZE="16"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,2" COLOR="#00b439">
<font SIZE="14"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,3" COLOR="#990000">
<font SIZE="12"/>
</stylenode>
<stylenode LOCALIZED_TEXT="AutomaticLayout.level,4" COLOR="#111111">
<font SIZE="10"/>
</stylenode>
</stylenode>
</stylenode>
</map_styles>
</hook>
<hook NAME="AutomaticEdgeColor" COUNTER="1"/>
<richcontent TYPE="DETAILS">

<html>
  <head>
    
  </head>
  <body>
    <p>
      Created in September 2015 together with `asciidoc3.py` to understand the internal structure and the approach better.
    </p>
  </body>
</html>
</richcontent>
<node TEXT="structure of asciidoc.py (Python 2 implementation)" POSITION="right" ID="ID_1273295101" CREATED="1442487874781" MODIFIED="1442487940461">
<edge COLOR="#ff0000" WIDTH="2"/>
<node TEXT="Program constants." ID="ID_1149030057" CREATED="1442488073837" MODIFIED="1442488077259"/>
<node TEXT="Utility functions and classes." ID="ID_425371104" CREATED="1442488078670" MODIFIED="1442488100281">
<node TEXT="classes" ID="ID_416070821" CREATED="1442488346557" MODIFIED="1442488348822">
<node TEXT="EAsciiDoc exception class" ID="ID_1691198825" CREATED="1442488350877" MODIFIED="1442488364425"/>
<node TEXT="OrderedDict" ID="ID_1882798739" CREATED="1442488364829" MODIFIED="1442488371783"/>
<node TEXT="AttrDict" ID="ID_1883878366" CREATED="1442519751032" MODIFIED="1442519778878"/>
<node TEXT="InsensitiveDict" ID="ID_409658801" CREATED="1442519788368" MODIFIED="1442519794628"/>
<node TEXT="Trace" ID="ID_1242122290" CREATED="1442519812407" MODIFIED="1442519828012"/>
<node TEXT="Message" ID="ID_65362889" CREATED="1442519828647" MODIFIED="1442519832556"/>
<node TEXT="" ID="ID_1494138374" CREATED="1442519833118" MODIFIED="1442519833118"/>
</node>
<node TEXT="functions" ID="ID_579026515" CREATED="1442488336813" MODIFIED="1442488345971">
<node TEXT="xopen()" ID="ID_1270499839" CREATED="1442488377910" MODIFIED="1442519935994"><richcontent TYPE="DETAILS" HIDDEN="true">

<html>
  <head>
    
  </head>
  <body>
    <p>
      Wraps the standard open() built in to convert the Python 2 interface, adding encoding for the Python 3 version of open().
    </p>
  </body>
</html>

</richcontent>
</node>
<node TEXT="userdir" ID="ID_1854943374" CREATED="1442519931574" MODIFIED="1442519946603"/>
<node TEXT="loalapp" ID="ID_998896682" CREATED="1442519947062" MODIFIED="1442519959155"/>
<node TEXT="file_in" ID="ID_1412590937" CREATED="1442519959797" MODIFIED="1442519968235"/>
<node TEXT="safe" ID="ID_1294530421" CREATED="1442519968814" MODIFIED="1442519977475"/>
<node TEXT="is_safe_file" ID="ID_916989026" CREATED="1442519978023" MODIFIED="1442519990427"/>
<node TEXT="safe_filename" ID="ID_397204123" CREATED="1442519991214" MODIFIED="1442520029291"/>
<node TEXT="..." ID="ID_1194941521" CREATED="1442520029735" MODIFIED="1442520057715"/>
</node>
</node>
<node TEXT="Document element classes." ID="ID_1381231235" CREATED="1442487940477" MODIFIED="1442520593107">
<edge COLOR="#006600"/>
<node TEXT="Document" ID="ID_1422875392" CREATED="1442488031509" MODIFIED="1442488034540"/>
<node TEXT="Header" ID="ID_1761181793" CREATED="1442488061213" MODIFIED="1442520186330"/>
<node TEXT="AttributeEntry" ID="ID_406481601" CREATED="1442520186878" MODIFIED="1442520201842"/>
<node TEXT="AttributeList" ID="ID_445823412" CREATED="1442520202334" MODIFIED="1442520244434"/>
<node TEXT="BlockTitle" ID="ID_659032277" CREATED="1442520228437" MODIFIED="1442520257530"/>
<node TEXT="Title" ID="ID_1387210726" CREATED="1442520258038" MODIFIED="1442520266626"/>
<node TEXT="FloatingTitle" ID="ID_316627282" CREATED="1442520267190" MODIFIED="1442520282874"/>
<node TEXT="Section" ID="ID_239434843" CREATED="1442520283541" MODIFIED="1442520291842"/>
<node TEXT="AbstractBlock" ID="ID_1838288570" CREATED="1442520292445" MODIFIED="1442520310338"/>
<node TEXT="AbstractBlocks" ID="ID_508509489" CREATED="1442520312037" MODIFIED="1442520341154"/>
<node TEXT="Paragraph" ID="ID_761230998" CREATED="1442520342092" MODIFIED="1442520353322"/>
<node TEXT="Paragraphs" ID="ID_1961069970" CREATED="1442520353718" MODIFIED="1442520372074"/>
<node TEXT="List" ID="ID_1724301102" CREATED="1442520385725" MODIFIED="1442520387801"/>
<node TEXT="Lists" ID="ID_241523930" CREATED="1442520388260" MODIFIED="1442520399554"/>
<node TEXT="DelimitedBlock" ID="ID_742828395" CREATED="1442520405300" MODIFIED="1442520417730"/>
<node TEXT="DelimitedBlocks" ID="ID_761597151" CREATED="1442520418445" MODIFIED="1442520440442"/>
<node TEXT="Column" ID="ID_486684108" CREATED="1442520440820" MODIFIED="1442520456850"/>
<node TEXT="Cell" ID="ID_1623341974" CREATED="1442520457653" MODIFIED="1442520464297"/>
<node TEXT="Table" ID="ID_491513643" CREATED="1442520472421" MODIFIED="1442520475033"/>
<node TEXT="Tables" ID="ID_1081296784" CREATED="1442520475437" MODIFIED="1442520497457"/>
<node TEXT="Macros" ID="ID_828977290" CREATED="1442520512229" MODIFIED="1442520516041"/>
<node TEXT="Macro" ID="ID_1976523483" CREATED="1442520516980" MODIFIED="1442520535810"/>
<node TEXT="CalloutMap" ID="ID_1296736564" CREATED="1442520569533" MODIFIED="1442520574265"/>
</node>
<node TEXT="Input stream Reader and output stream writer classes." ID="ID_1284734155" CREATED="1442488121255" MODIFIED="1442488123286">
<node TEXT="Reader1" ID="ID_1152253798" CREATED="1442520613270" MODIFIED="1442520618817"/>
<node TEXT="Reader" ID="ID_252423896" CREATED="1442520619411" MODIFIED="1442520631489"/>
<node TEXT="Writer" ID="ID_824958130" CREATED="1442520631929" MODIFIED="1442520641617"/>
</node>
<node TEXT="Configuration file processing." ID="ID_953082447" CREATED="1442488133303" MODIFIED="1442488135413">
<node TEXT="class Config" ID="ID_1291725553" CREATED="1442520688317" MODIFIED="1442520717233"/>
</node>
<node TEXT="Deprecated old table classes." ID="ID_1954366356" CREATED="1442488157512" MODIFIED="1442488162856"/>
<node TEXT="Filter and theme plugin commands." ID="ID_1449031160" CREATED="1442488188760" MODIFIED="1442488194167"/>
<node TEXT="Application code." ID="ID_1064400510" CREATED="1442488205881" MODIFIED="1442488209521">
<node TEXT="Constants" ID="ID_968365897" CREATED="1442488209521" MODIFIED="1442488220068"/>
<node TEXT="Globals" ID="ID_1602305897" CREATED="1442488220761" MODIFIED="1442488224964"/>
<node TEXT="Functions" ID="ID_1952826778" CREATED="1442488273723" MODIFIED="1442488276988"/>
</node>
<node TEXT="Main body" ID="ID_1216713732" CREATED="1442488278611" MODIFIED="1442488286189"/>
</node>
</node>
</map>
