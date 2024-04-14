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
@TableName("spatial_ref_sys")
@ApiModel(value = "SpatialRefSys对象", description = "")
public class SpatialRefSys implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableField("srid")
    private Integer srid;

    @TableField("auth_name")
    private String authName;

    @TableField("auth_srid")
    private Integer authSrid;

    @TableField("srtext")
    private String srtext;

    @TableField("proj4text")
    private String proj4text;


}
