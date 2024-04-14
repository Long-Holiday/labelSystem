package com.example.labelMark.domain;

import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 * 
 * </p>
 *
 * @author wh
 * @since 2024-04-12
 */
@Getter
@Setter
@TableName("sampleimg")
@ApiModel(value = "Sampleimg对象", description = "")
public class Sampleimg implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableField("imgid")
    private Integer imgid;

    @TableField("sampleid")
    private Integer sampleid;

    @TableField("imgsrc")
    private String imgsrc;

    @TableField("typeid")
    private Integer typeid;


}
