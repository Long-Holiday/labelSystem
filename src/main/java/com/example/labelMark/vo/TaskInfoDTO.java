package com.example.labelMark.vo;

import lombok.Data;

import java.util.Date;
import java.util.List;
import java.util.Map;

/**
 * @Description 用于getTaskInfo方法数据接收
 * @Author wh
 * @Date 2024/5/14
 */
@Data
public class TaskInfoDTO {
    private int taskid;
    private String taskname;
    private String markTable;
    private String type;
    private String mapserver;
    private String daterange;
    private Integer status;
    private String auditfeedback;
    private int userid;
    private String username;
    private int id;
    private String typeArr;
    private List<Map<String, Object>> userArr;
}
