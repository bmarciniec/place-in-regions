<?xml version="1.0" encoding="utf-8"?>
<Element>
    <Script>
        <Name>PlaceInRegions.py</Name>
        <Title>Place in regions</Title>
        <Version>0.1</Version>
        <ShowFavoriteButtons>False</ShowFavoriteButtons>
    </Script>
    <Page>
        <Name>Placement</Name>
        <Text>General</Text>
        <Parameter>
            <Name>PlacementType</Name>
            <Text>Placement type</Text>
            <Value>1</Value>
            <ValueType>RadioButtonGroup</ValueType>

            <Parameter>
                <Name>LinearPlacementType</Name>
                <Text>linear</Text>
                <Value>1</Value>
                <ValueType>RadioButton</ValueType>
            </Parameter>
            <Parameter>
                <Name>PolygonalPlacementType</Name>
                <Text>polygonal</Text>
                <Value>2</Value>
                <ValueType>RadioButton</ValueType>
            </Parameter>
        </Parameter>
        <Parameter>
            <Name>Separator</Name>
            <ValueType>Separator</ValueType>
        </Parameter>
        <Parameter>
            <Name>RegionsString</Name>
            <Text>Placement regions</Text>
            <Value>5*100+$*200+5*100</Value>
            <ValueType>String</ValueType>
        </Parameter>
    </Page>
</Element>
