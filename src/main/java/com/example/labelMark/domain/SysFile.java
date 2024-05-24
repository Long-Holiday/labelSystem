package com.example.labelMark.domain;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import java.io.Serializable;
import io.swagger.annotations.ApiModel;
import lombok.Getter;
import lombok.Setter;

/**
 * <p>
 *
 * </p>
 *
 * @author hjw
 * @since 2024-04-18
 */
@Getter
@Setter
@TableName("file")
@ApiModel(value = "File对象", description = "")
public class SysFile implements Serializable {

    private static final long serialVersionUID = 1L;

    @TableId(value = "file_id", type = IdType.AUTO)
    private Integer fileId;

    @TableField("file_name")
    private String fileName;

    @TableField("update_time")
    private String updateTime;

    @TableField("status")
    private Integer status;

    @TableField("size")
    private String size;

}
