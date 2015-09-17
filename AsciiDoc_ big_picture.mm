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
<node TEXT="functions" ID="ID_579026515" CREATED="1442488336813" MODIFIED="1442488345971">
<node TEXT="xopen()" ID="ID_1270499839" CREATED="1442488377910" MODIFIED="1442497735687">
<icon BUILTIN="pencil"/>
<richcontent TYPE="DETAILS">

<html>
  <head>
    
  </head>
  <body>
    <p>
      Wraps the standard
    </p>
  </body>
</html>

</richcontent>
</node>
</node>
<node TEXT="classes" ID="ID_416070821" CREATED="1442488346557" MODIFIED="1442488348822">
<node TEXT="EAsciiDoc exception class" ID="ID_1691198825" CREATED="1442488350877" MODIFIED="1442488364425"/>
<node TEXT="OrderedDict" ID="ID_1882798739" CREATED="1442488364829" MODIFIED="1442488371783"/>
</node>
</node>
<node TEXT="Document element classes." ID="ID_1381231235" CREATED="1442487940477" MODIFIED="1442488029997">
<node TEXT="" ID="ID_1761181793" CREATED="1442488061213" MODIFIED="1442488061213"/>
<node TEXT="Document" ID="ID_1422875392" CREATED="1442488031509" MODIFIED="1442488034540"/>
</node>
<node TEXT="Input stream Reader and output stream writer classes." ID="ID_1284734155" CREATED="1442488121255" MODIFIED="1442488123286"/>
<node TEXT="Configuration file processing." ID="ID_953082447" CREATED="1442488133303" MODIFIED="1442488135413"/>
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
