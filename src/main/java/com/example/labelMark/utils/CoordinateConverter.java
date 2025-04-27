package com.example.labelMark.utils;

import cn.hutool.core.bean.BeanUtil;
import cn.hutool.core.convert.Convert;
import cn.hutool.core.map.MapBuilder;
import cn.hutool.core.map.MapUtil;
import cn.hutool.core.util.ObjectUtil;
import cn.hutool.core.util.StrUtil;
import com.example.labelMark.domain.Mark;
import com.example.labelMark.domain.Type;
import com.example.labelMark.service.TypeService;

import javax.annotation.Resource;
import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;


public class CoordinateConverter {
    @Resource
    static
    TypeService typeService;

    //转化坐标信息（geojson）
    public static List<Map<String, Object>> convertCoordinate(List<Map<String, Object>> geojsonArr) {
        List<Map<String, Object>> geometryArr = new ArrayList<>();

        for (Map<String, Object> item : geojsonArr) {
//            标注多边形信息
            List<Object> extentArr = (List<Object>) item.get("extentArr");
            Integer typeId = (Integer) item.get("typeId");

            if (extentArr != null) {
                for (Object featureAndMarkId : extentArr) {
                    StringBuilder itemArr = new StringBuilder();
//                    解析markId
                    Map featureAndMarkIdMap = (Map<?, ?>) featureAndMarkId;
                    Object markIdObj = featureAndMarkIdMap.get("markId");
                    String markId =ObjectUtil.isNotNull(markIdObj)
                            ?markIdObj.toString():null;
                    flattenCoordinates(featureAndMarkIdMap.get("feature"), itemArr);

                    Map<String, Object> geometryMap = new HashMap<>();
                    geometryMap.put("geom", itemArr.toString());
                    geometryMap.put("typeId", typeId);
                    geometryMap.put("markId", markId);

                    geometryArr.add(geometryMap);
                }
            }
        }

        return geometryArr;
    }

    private static void flattenCoordinates(Object feature, StringBuilder itemArr) {
        if (feature instanceof List) {
            for (Object element : (List<?>) feature) {
                flattenCoordinates(element, itemArr);
            }
        } else {
            if (itemArr.length() > 0) {
                itemArr.append(", ");
            }
            itemArr.append(feature.toString());
        }
    }

    //处理标注信息
    public static List<Map<String, Object>> processMarkInfo(List<Map<String, Object>> geometryArr, List<Type> typeArr) {
        List<Map<String, Object>> markInfoArr = new ArrayList<>();

        for (Type type : typeArr) {
            markInfoArr = geometryArr.stream()
                    //TODO 改一下命名规范typeid--->typeId
                    .filter(item -> type.getTypeId().equals(item.get("typeId")))
                    .collect(Collectors.toList());
        }
        return markInfoArr;

        // 处理 markInfoArr，例如保存数据到数据库
        // ...
    }

    public static List<Map<String, Object>> convertGeojson(List<Mark> marks) {
        List<Map<String, Object>> list = new ArrayList<>();
        marks.forEach(mark -> {
            List<List<Double[]>> coordinatesArr = new ArrayList<>();
            String geom = mark.getGeom();
            String[] geomString = geom.split(", ");
//            字符串转为数值
            Double[] doubles = Convert.toDoubleArray(geomString);
            List<Double[]> doublesList = new ArrayList<>();
            for (int i = 0; i <= (doubles.length - 1) / 2; i++) {
                Double[] doubles1 = Arrays.copyOfRange(doubles, i * 2, i * 2 + 2);
                doublesList.add(doubles1);
            }
            coordinatesArr.add(doublesList);
            List<List<List<Double[]>>> coordinatesPolygonArr = new ArrayList<>();
            coordinatesPolygonArr.add(coordinatesArr);
            Map<String, Object> geometry = MapUtil.builder(new HashMap<String, Object>())
                    .put("type", "MultiPolygon")
                    .put("coordinates", coordinatesPolygonArr)
                    .build();

            Map<String, Object> features = MapUtil.builder(new HashMap<String, Object>())
                    .put("type", "Feature")
                    .put("geometry", geometry)
                    .build();

            ArrayList<Map<String, Object>> maps = new ArrayList<>();
            maps.add(features);

            Map<String, Object> markGeoJson = MapUtil.builder(new HashMap<String, Object>())
                    .put("typeId", mark.getTypeId())
                    .put("markId", mark.getId())
                    .put("markGeoJson", new HashMap<String, Object>() {{
                        put("type", "FeatureCollection");
                        put("features", maps);
                        put("crs", new HashMap<String, Object>() {{
                            put("type", "name");
                            put("properties",
                                    new HashMap<String, Object>() {{
                                        put("name", "EPSG:3857");
                                    }});
                        }});
                    }})
                    .build();
            list.add(markGeoJson);
        });
        return list;
    }
}

